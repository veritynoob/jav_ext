import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from page_utils import is_cloudflare_challenge


def load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_is_cloudflare_challenge_on_cf_page():
    html = load_fixture("cf_challenge.html")
    assert is_cloudflare_challenge(html) is True


def test_is_cloudflare_challenge_on_checkbox_page():
    html = load_fixture("cf_challenge_checkbox.html")
    assert is_cloudflare_challenge(html) is True


def test_is_cloudflare_challenge_on_javlibrary_page():
    html = load_fixture("most_wanted.html")
    assert is_cloudflare_challenge(html) is False


def test_is_cloudflare_challenge_on_search_page():
    html = load_fixture("search_result.html")
    assert is_cloudflare_challenge(html) is False


def test_is_cloudflare_challenge_on_empty_html():
    assert is_cloudflare_challenge("<html><body></body></html>") is False


def test_is_cloudflare_challenge_on_blank_page():
    assert is_cloudflare_challenge("<html><head><title>Welcome</title></head><body></body></html>") is False
