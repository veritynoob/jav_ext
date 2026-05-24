import os

JAVLIBRARY_BASE_URL = "https://www.javlibrary.com"
MOST_WANTED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_mostwanted.php"
TOP_RATED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_toprated.php"

SEARCH_BASE_URL = "https://clg55.top"

PROXY = os.environ.get("JAV_PROXY")
WAIT_DELAY = int(os.environ.get("JAV_WAIT_DELAY", "40"))
COVERS_DIR = os.environ.get("JAV_COVERS_DIR", "covers")
DATA_DIR = os.environ.get("JAV_DATA_DIR", "data")
MAGNET_BACKFILL_DAYS = int(os.environ.get("JAV_MAGNET_BACKFILL_DAYS", "60"))
MAX_BACKFILL_COUNT = int(os.environ.get("JAV_MAX_BACKFILL_COUNT", "20"))
REQUEST_RETRIES = 3
WAIT_MIN = int(os.environ.get("JAV_WAIT_MIN", "5"))
WAIT_MAX = int(os.environ.get("JAV_WAIT_MAX", "15"))

# Web panel config
WEB_HOST = os.environ.get("JAV_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("JAV_WEB_PORT", "8000"))
WEB_PASSWORD = os.environ.get("JAV_WEB_PASSWORD", "admin")
WEB_SECRET_KEY = os.environ.get("JAV_WEB_SECRET_KEY", "change-me-in-production")
