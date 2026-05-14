import os

JAVLIBRARY_BASE_URL = "https://www.javlibrary.com"
MOST_WANTED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_mostwanted.php"
TOP_RATED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_toprated.php"

SEARCH_BASE_URL = "https://clg55.top"

PROXY = os.environ.get("JAV_PROXY", "http://127.0.0.1:7897")
WAIT_DELAY = int(os.environ.get("JAV_WAIT_DELAY", "40"))
COVERS_DIR = os.environ.get("JAV_COVERS_DIR", "covers")
DATA_DIR = os.environ.get("JAV_DATA_DIR", "data")
MAGNET_BACKFILL_DAYS = int(os.environ.get("JAV_MAGNET_BACKFILL_DAYS", "60"))
MAX_BACKFILL_COUNT = int(os.environ.get("JAV_MAX_BACKFILL_COUNT", "20"))
REQUEST_RETRIES = 3
PAGE_INTERVAL_MIN = 3
PAGE_INTERVAL_MAX = 5
