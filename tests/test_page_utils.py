import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.page_utils import is_cloudflare_challenge


def load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# Fixture-based tests
# =============================================================================


def test_cf_challenge_detected_on_js_page():
    assert is_cloudflare_challenge(load_fixture("cf_challenge.html")) is True


def test_cf_challenge_detected_on_checkbox_page():
    assert is_cloudflare_challenge(load_fixture("cf_challenge_checkbox.html")) is True


def test_cf_challenge_not_detected_on_javlibrary():
    assert is_cloudflare_challenge(load_fixture("most_wanted.html")) is False


def test_cf_challenge_not_detected_on_search():
    assert is_cloudflare_challenge(load_fixture("search_result.html")) is False


def test_cf_challenge_not_detected_on_empty():
    assert is_cloudflare_challenge("<html><body></body></html>") is False


def test_cf_challenge_not_detected_on_blank():
    assert is_cloudflare_challenge("<html><head><title>Welcome</title></head><body></body></html>") is False


# =============================================================================
# Title pattern tests — each CF title pattern detected in isolation
# =============================================================================


def test_cf_title_just_a_moment():
    html = "<html><head><title>Just a moment...</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_title_checking_your_browser():
    html = "<html><head><title>Checking your browser before accessing</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_title_please_wait():
    html = "<html><head><title>Please Wait... | Cloudflare</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_title_ddos_protection():
    html = "<html><head><title>DDoS protection by Cloudflare</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_title_attention_required():
    html = "<html><head><title>Attention Required! | Cloudflare</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_title_cloudflare_in_title():
    html = "<html><head><title>Cloudflare</title></head><body></body></html>"
    assert is_cloudflare_challenge(html) is True


# =============================================================================
# HTML marker tests — each CF HTML marker detected in isolation
# =============================================================================


def test_cf_marker_cf_chl_opt():
    html = "<html><body><script>window.__cf_chl_opt = {};</script></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_marker_browser_verification():
    html = "<html><body><div class='cf-browser-verification'></div></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_marker_turnstile():
    html = "<html><body><div class='cf-turnstile'></div></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_marker_challenge_running():
    html = "<html><body><div id='cf-challenge-running'></div></body></html>"
    assert is_cloudflare_challenge(html) is True


def test_cf_marker_chl_widget():
    html = "<html><body><div class='cf-chl-widget'></div></body></html>"
    assert is_cloudflare_challenge(html) is True


# =============================================================================
# Negative pattern tests — legitimate pages that should NOT match
# =============================================================================


def test_legitimate_page_with_cloud_in_text():
    """A page mentioning 'cloud' innocuously should not be flagged."""
    html = "<html><head><title>Cloud Storage Solutions</title></head><body><p>cloud computing</p></body></html>"
    assert is_cloudflare_challenge(html) is False


def test_legitimate_page_with_turnstile_in_text():
    """A page using the word 'turnstile' in normal content should not be flagged."""
    html = "<html><head><title>Metro Station</title></head><body><p>Insert ticket at turnstile</p></body></html>"
    assert is_cloudflare_challenge(html) is False


def test_legitimate_page_with_widget_in_class():
    """A page with a non-CF widget class should not be flagged."""
    html = "<html><body><div class='chat-widget'></div></body></html>"
    assert is_cloudflare_challenge(html) is False


def test_legitimate_javascript_page():
    """A page with typical JavaScript but no CF markers should not be flagged."""
    html = """<html><head><title>My App</title>
    <script>window.appConfig = {version: '1.0'};</script></head>
    <body><div class="container"><p>Hello</p></div></body></html>"""
    assert is_cloudflare_challenge(html) is False
