import logging
import time
from bs4 import BeautifulSoup
from cloakbrowser import launch

logger = logging.getLogger(__name__)

_CF_TITLE_PATTERNS = [
    "just a moment",
    "checking your browser",
    "please wait",
    "cloudflare",
    "ddos protection",
    "attention required",
]

_CF_HTML_MARKERS = [
    "__cf_chl_opt",
    "cf-browser-verification",
    "cf-turnstile",
    "cf-challenge-running",
    "cf-chl-widget",
]


def is_cloudflare_challenge(html):
    """Detect if the page HTML is a Cloudflare challenge page."""
    lower = html.lower()
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.text.strip().lower() if soup.title else ""

    if any(pattern in title for pattern in _CF_TITLE_PATTERNS):
        return True
    if any(marker in lower for marker in _CF_HTML_MARKERS):
        return True
    return False


def bypass_cloudflare(page):
    """Attempt to bypass a Cloudflare checkbox challenge.

    Presses Tab then Space to focus and check the Cloudflare verification checkbox.
    This follows the approach demonstrated in the a.py reference script.
    """
    logger.info("Attempting Cloudflare bypass (Tab+Space)...")
    try:
        page.keyboard.press("Tab")
        time.sleep(0.3)
        page.keyboard.press("Space")
        logger.info("Tab+Space pressed for Cloudflare checkbox interaction")
    except Exception as e:
        logger.warning(f"Bypass keyboard interaction failed: {e}")


def _wait_cf_resolved(page, timeout=60, poll_interval=2):
    """Poll until Cloudflare challenge is resolved (CF markers disappear from page).

    Returns page HTML once resolved, or None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            html = page.content()
        except Exception:
            time.sleep(poll_interval)
            continue

        if is_cloudflare_challenge(html):
            logger.info(f"Cloudflare still present, waiting... ({int(deadline - time.time())}s remaining)")
        else:
            logger.info("Cloudflare challenge resolved")
            return html

        time.sleep(poll_interval)

    logger.warning(f"Timed out after {timeout}s waiting for Cloudflare to resolve")
    return None


def load_with_cf_bypass(url, *, proxy=None, headless=False, wait=40, timeout=60, poll_interval=2):
    """Load a URL, detecting and bypassing Cloudflare protection if needed.

    Fully self-contained: launches a browser, navigates, handles Cloudflare,
    returns the page HTML, and closes the browser before returning.

    This is a generic utility that works with any Cloudflare-protected website.
    The flow matches the approach from a.py:
      1. Launch browser
      2. Navigate to the URL
      3. Wait for initial page load
      4. Check if we hit a Cloudflare challenge page
      5. If yes, attempt bypass (Tab+Space) and wait for the challenge to resolve
      6. Return the HTML, close the browser

    Args:
        url: The target URL to load.
        proxy: Optional proxy URL (e.g. "http://127.0.0.1:7897").
        headless: Run browser in headless mode. Default False.
        wait: Seconds to wait after navigation before checking page state.
        timeout: Max seconds to wait for Cloudflare challenge to resolve.
        poll_interval: Seconds between page content checks.

    Returns:
        HTML string on success, or None if the page failed to load past Cloudflare.
    """
    browser = None
    try:
        browser = launch(proxy=proxy, humanize=True, headless=headless)
        page = browser.new_page()
        page.goto(url)
        logger.info(f"Navigated to {url}, waiting {wait}s for page load...")
        time.sleep(wait)

        html = page.content()
        if is_cloudflare_challenge(html):
            logger.info("Cloudflare challenge detected")
            bypass_cloudflare(page)
            html = _wait_cf_resolved(page, timeout=timeout, poll_interval=poll_interval)
            if html is None:
                logger.error("Failed to bypass Cloudflare challenge")
        else:
            logger.info("No Cloudflare challenge detected, page loaded directly")
            html = _wait_cf_resolved(page, timeout=min(10, timeout), poll_interval=poll_interval)
            if html is None:
                html = page.content()

        return html
    except Exception as e:
        logger.error(f"Failed to load {url}: {e}")
        return None
    finally:
        if browser is not None:
            try:
                page.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
