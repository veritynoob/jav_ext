import logging
import random
import sys
import time
from config import (
    MOST_WANTED_URL, TOP_RATED_URL, SEARCH_BASE_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, REQUEST_RETRIES,
    PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX,
)
from scraper import parse_list_page, parse_search_page, is_javlibrary_page
from page_utils import load_with_cf_bypass
from db import (
    init_db, upsert_video, save_actresses, save_magnets,
    save_rankings, get_videos_missing_magnets, update_video_search_url,
    update_video_cover_path,
)
from downloader import download_cover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def random_delay():
    delay = random.uniform(PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX)
    logger.info(f"Sleeping {delay:.1f}s...")
    time.sleep(delay)


def scrape_list(url, list_type):
    logger.info(f"Fetching {list_type}: {url}")
    for attempt in range(REQUEST_RETRIES):
        try:
            html = load_with_cf_bypass(url, proxy=PROXY, wait=WAIT_DELAY, timeout=60)
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


def scrape_magnets(code):
    search_url = f"{SEARCH_BASE_URL}/search/{code}"
    logger.info(f"Searching magnets for {code}")
    for attempt in range(REQUEST_RETRIES):
        try:
            html = load_with_cf_bypass(search_url, proxy=PROXY, wait=random.uniform(3, 5), timeout=30)
            if html is None:
                raise Exception(f"Failed to load search page past Cloudflare (code={code})")
            if not is_javlibrary_page(html):
                raise Exception(f"Loaded page is not expected content (code={code})")
            _, magnets = parse_search_page(html, search_url)
            logger.info(f"Found {len(magnets)} magnets for {code}")
            return search_url, magnets
        except Exception as e:
            logger.warning(f"Magnet attempt {attempt+1}/{REQUEST_RETRIES} failed for {code}: {e}")
            if attempt < REQUEST_RETRIES - 1:
                random_delay()
    return search_url, []


def main():
    logger.info("Starting JavLibrary scraper")

    conn = init_db()
    try:
        # 1. Scrape list pages
        all_items = {}
        for url, list_type in [(MOST_WANTED_URL, "most_wanted"), (TOP_RATED_URL, "top_rated")]:
            items = scrape_list(url, list_type)
            for idx, item in enumerate(items):
                code = item["code"]
                if code not in all_items:
                    all_items[code] = item

                upsert_video(conn, item)
                save_actresses(conn, code, item.get("actresses", []))
                logger.info(f"Saved {code}: {item.get('title','')[:40]}")

                if item.get("cover_url"):
                    path = download_cover(code, item["cover_url"], COVERS_DIR)
                    if path:
                        update_video_cover_path(conn, code, path)
                        logger.info(f"Cover saved: {path}")

            ranking_entries = [(item["code"], list_type, idx + 1) for idx, item in enumerate(items)]
            save_rankings(conn, list_type, ranking_entries)

            random_delay()

        # 2. Fetch magnets for new videos
        logger.info("Fetching magnets for new videos...")
        for code in all_items:
            search_url, magnets = scrape_magnets(code)
            if search_url:
                update_video_search_url(conn, code, search_url)
            if magnets:
                save_magnets(conn, code, magnets)
            random_delay()

        # 3. Backfill missing magnets for recent videos
        logger.info(f"Backfilling magnets (within {MAGNET_BACKFILL_DAYS} days)...")
        missing_codes = get_videos_missing_magnets(conn, days=MAGNET_BACKFILL_DAYS, limit=MAX_BACKFILL_COUNT)
        logger.info(f"Found {len(missing_codes)} videos needing magnet backfill")
        for code in missing_codes:
            search_url, magnets = scrape_magnets(code)
            if search_url:
                update_video_search_url(conn, code, search_url)
            if magnets:
                save_magnets(conn, code, magnets)
            random_delay()

        logger.info("Scrape complete")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
