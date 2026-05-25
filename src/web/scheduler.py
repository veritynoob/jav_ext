import logging
import threading
import time

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 48 * 3600  # 2 days


def _run_loop():
    # Spread initial run: first scrape after 2-4h, then every 48h
    initial_delay = 2 * 3600 + hash(time.time()) % (2 * 3600)
    logger.info(f"Scheduler: first scrape in {initial_delay / 3600:.1f}h, then every {INTERVAL_SECONDS / 3600:.0f}h")
    time.sleep(initial_delay)

    while True:
        logger.info("Scheduler: starting scheduled scrape")
        try:
            from src.main import scrape_full
            scrape_full()
            logger.info("Scheduler: scheduled scrape complete")
        except Exception as e:
            logger.error(f"Scheduler: scrape failed: {e}")
        time.sleep(INTERVAL_SECONDS)


def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_run_loop, daemon=True)
    t.start()
    logger.info("Scheduler: background thread started")
    return t
