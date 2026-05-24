import logging
import random
import sys
import time
from src.config import (
    MOST_WANTED_URL, TOP_RATED_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, REQUEST_RETRIES, WAIT_MIN, WAIT_MAX,
)
from src.scraper import parse_list_page, parse_detail_page, is_javlibrary_page
from src.page_utils import load_with_cf_bypass
from src.db import (
    init_db, upsert_video, save_actresses,
    save_rankings, update_video_cover_path,
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
            items = parse_list_page(html)
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
    conn = init_db()
    stats = {"succeeded": 0, "skipped": 0, "failed": 0}
    consecutive_failures = 0

    try:
        all_items = {}
        for url, list_type in [(MOST_WANTED_URL, "most_wanted"), (TOP_RATED_URL, "top_rated")]:
            items = scrape_list(url, list_type)
            ranking_entries = []
            for idx, item in enumerate(items):
                code = item["code"]
                if code not in all_items:
                    all_items[code] = item
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
    finally:
        conn.close()


def main():
    scrape_all()


if __name__ == "__main__":
    main()
