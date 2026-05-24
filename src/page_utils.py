import asyncio
import logging
import time
from bs4 import BeautifulSoup

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


async def _bypass_cloudflare(page):
    logger.info("Attempting Cloudflare bypass (Tab+Space)...")
    try:
        await page.keyboard.press("Tab")
        await asyncio.sleep(0.3)
        await page.keyboard.press("Space")
        logger.info("Tab+Space pressed for Cloudflare checkbox interaction")
    except Exception as e:
        logger.warning(f"Bypass keyboard interaction failed: {e}")


async def _wait_cf_resolved(page, timeout=60, poll_interval=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            html = await page.content()
        except Exception:
            await asyncio.sleep(poll_interval)
            continue

        if is_cloudflare_challenge(html):
            logger.info(f"Cloudflare still present, waiting... ({int(deadline - time.time())}s remaining)")
        else:
            logger.info("Cloudflare challenge resolved")
            return html

        await asyncio.sleep(poll_interval)

    logger.warning(f"Timed out after {timeout}s waiting for Cloudflare to resolve")
    return None


async def _load_async(url, *, proxy=None, headless=False, wait=40, timeout=60, poll_interval=2):
    from cloakbrowser import launch_async

    launch_kwargs = {"humanize": True, "headless": headless}
    if proxy:
        launch_kwargs["proxy"] = proxy

    browser = await launch_async(**launch_kwargs)
    try:
        page = await browser.new_page()
        await page.goto(url)
        logger.info(f"Navigated to {url}, waiting {wait}s for page load...")
        await asyncio.sleep(wait)

        html = await page.content()
        if is_cloudflare_challenge(html):
            logger.info("Cloudflare challenge detected")
            await _bypass_cloudflare(page)
            html = await _wait_cf_resolved(page, timeout=timeout, poll_interval=poll_interval)
            if html is None:
                logger.error("Failed to bypass Cloudflare challenge")
            else:
                logger.info("Waiting for JS to render content after CF bypass...")
                await asyncio.sleep(wait)
                html = await page.content()
        else:
            logger.info("No Cloudflare challenge detected, page loaded directly")
            html = await _wait_cf_resolved(page, timeout=min(10, timeout), poll_interval=poll_interval)
            if html is None:
                html = await page.content()

        return html
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass


def load_with_cf_bypass(url, *, proxy=None, headless=False, wait=40, timeout=60, poll_interval=2):
    """Load a URL, detecting and bypassing Cloudflare protection if needed.

    Each call gets a fresh event loop via asyncio.run() to avoid the
    "Playwright Sync API inside the asyncio loop" error on repeated calls.
    """
    try:
        return asyncio.run(_load_async(
            url, proxy=proxy, headless=headless, wait=wait,
            timeout=timeout, poll_interval=poll_interval,
        ))
    except Exception as e:
        logger.error(f"Failed to load {url}: {e}")
        return None
