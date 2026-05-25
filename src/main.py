import argparse
import base64
import logging
import random
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so `from src.xxx` imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import (
    MOST_WANTED_URL, TOP_RATED_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, REQUEST_RETRIES, WAIT_MIN, WAIT_MAX,
    MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, SEARCH_BASE_URL,
)
from src.scraper import parse_list_page, parse_detail_page, is_javlibrary_page, parse_search_page, parse_search_detail_page
from src.page_utils import load_with_cf_bypass
from src.db import (
    init_db, upsert_video, save_actresses,
    save_rankings, update_video_cover_path,
    has_video_detail, get_videos_missing_magnets,
    update_video_search_url, save_magnets,
)
from src.downloader import download_cover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def random_delay():
    delay = random.uniform(WAIT_MIN, WAIT_MAX)
    logger.info(f"Sleeping {delay:.1f}s...")
    time.sleep(delay)


def scrape_list(url, list_type):
    logger.info(f"Fetching {list_type}: {url}")
    for attempt in range(REQUEST_RETRIES):
        try:
            html = load_with_cf_bypass(url, proxy=PROXY, wait=WAIT_DELAY, timeout=60, headless=True)
            if html is None:
                raise Exception(f"Failed to load page past Cloudflare (list_type={list_type})")
            if not is_javlibrary_page(html):
                raise Exception(f"Loaded page is not JavLibrary content (list_type={list_type})")
            items = parse_list_page(html, url)
            logger.info(f"Parsed {len(items)} items from {list_type}")
            return items
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{REQUEST_RETRIES} failed for {list_type}: {e}")
            if attempt < REQUEST_RETRIES - 1:
                random_delay()
    logger.error(f"All attempts failed for {list_type}")
    return []


def scrape_detail(code, detail_url):
    """Fetch and parse a single video detail page. Returns dict or None on failure."""
    logger.info(f"Fetching detail for {code}: {detail_url}")
    try:
        html = load_with_cf_bypass(detail_url, proxy=PROXY, wait=WAIT_DELAY, timeout=60, headless=True)
        if html is None:
            raise Exception("Failed to load detail page past Cloudflare")
        if not is_javlibrary_page(html):
            raise Exception("Loaded page is not JavLibrary content")
        detail = parse_detail_page(html)
        logger.info(f"Detail for {code}: score={detail.get('score')}, date={detail.get('date')}")
        return detail
    except Exception as e:
        logger.warning(f"Detail fetch failed for {code}: {e}")
        return None


MAX_CONSECUTIVE_FAILURES = 5


def scrape_all():
    """Main entry: scrape list pages, then detail page for each video."""
    logger.info("Starting JavLibrary scraper (list + detail mode)")
    conn = None
    stats = {"succeeded": 0, "skipped": 0, "failed": 0}
    consecutive_failures = 0

    try:
        conn = init_db()
        all_items = {}
        for url, list_type in [(MOST_WANTED_URL, "most_wanted"), (TOP_RATED_URL, "top_rated")]:
            items = scrape_list(url, list_type)
            ranking_entries = []
            for idx, item in enumerate(items):
                code = item["code"]
                if code not in all_items:
                    all_items[code] = item
                    upsert_video(conn, item)
                ranking_entries.append((code, list_type, idx + 1))
            save_rankings(conn, list_type, ranking_entries)
            random_delay()

        logger.info(f"Total unique videos from lists: {len(all_items)}")

        for code, item in list(all_items.items()):
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(f"Aborting after {MAX_CONSECUTIVE_FAILURES} consecutive failures")
                break

            detail_url = item.get("detail_url", "")
            if not detail_url:
                logger.warning(f"No detail_url for {code}, skipping")
                stats["skipped"] += 1
                continue

            if has_video_detail(conn, code):
                logger.info(f"Detail already exists for {code}, skipping")
                stats["skipped"] += 1
                continue

            random_delay()
            detail = scrape_detail(code, detail_url)
            if detail is None:
                stats["failed"] += 1
                consecutive_failures += 1
                continue

            consecutive_failures = 0
            stats["succeeded"] += 1

            # Merge: detail overrides list (higher quality cover_url)
            merged = {**item, **detail}
            upsert_video(conn, merged)
            save_actresses(conn, code, merged.get("actresses", []))
            logger.info(f"Saved {code}: {merged.get('title','')[:40]}")

            if merged.get("cover_url"):
                path = download_cover(code, merged["cover_url"], COVERS_DIR)
                if path:
                    update_video_cover_path(conn, code, path)
                    logger.info(f"Cover saved: {path}")

        logger.info(f"Scrape complete. Succeeded={stats['succeeded']}, Skipped={stats['skipped']}, Failed={stats['failed']}")
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


MAX_MAGNETS_PER_VIDEO = 2


def scrape_magnets():
    """Search clg55.top for magnets for videos that don't have them yet.

    Returns (processed: int, failed: int).
    """
    logger.info("Starting magnet backfill (clg55.top)")
    conn = None
    processed = 0
    failed = 0

    try:
        conn = init_db()
        codes = get_videos_missing_magnets(conn, days=MAGNET_BACKFILL_DAYS, limit=MAX_BACKFILL_COUNT)
        logger.info(f"Found {len(codes)} videos missing magnets (last {MAGNET_BACKFILL_DAYS} days, max {MAX_BACKFILL_COUNT})")

        for code in codes:
            logger.info(f"Searching magnets for {code}...")
            encoded = base64.b64encode(code.encode()).decode()
            search_url = f"{SEARCH_BASE_URL}/search?word={encoded}&sort=rele"
            html = load_with_cf_bypass(search_url, proxy=PROXY, wait=random.uniform(3, 5), timeout=30, headless=True)
            if not html:
                failed += 1
                continue

            update_video_search_url(conn, code, search_url)
            _, results = parse_search_page(html, search_url)
            saved = 0
            for detail_url, title, download_count in results:
                if code.upper() not in title.upper():
                    continue
                time.sleep(random.uniform(2, 4))
                detail_html = load_with_cf_bypass(detail_url, proxy=PROXY, wait=random.uniform(3, 5), timeout=30, headless=True)
                if detail_html:
                    info = parse_search_detail_page(detail_html)
                    if info:
                        info["download_count"] = download_count
                        save_magnets(conn, code, [info])
                        saved += 1
                        logger.info(f"  Magnet saved for {code} ({saved}/{MAX_MAGNETS_PER_VIDEO})")
                        if saved >= MAX_MAGNETS_PER_VIDEO:
                            break
            processed += 1
            time.sleep(random.uniform(3, 5))

        logger.info(f"Magnet backfill complete. Processed={processed}, Failed={failed}")
        return processed, failed
    except Exception as e:
        logger.error(f"Magnet backfill failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


def scrape_full():
    """Run JAV list+detail scraping, then magnet backfill."""
    logger.info("=== Starting full scrape (JAV + magnets) ===")
    scrape_all()
    scrape_magnets()
    logger.info("=== Full scrape complete ===")


def main():
    parser = argparse.ArgumentParser(description="JAV Scraper")
    parser.add_argument("--full", action="store_true", help="Run full scrape: JAV lists+details then magnet backfill")
    parser.add_argument("--magnets", action="store_true", help="Run only magnet backfill")
    args = parser.parse_args()

    if args.magnets:
        scrape_magnets()
    elif args.full:
        scrape_full()
    else:
        scrape_all()


if __name__ == "__main__":
    main()
