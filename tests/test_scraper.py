import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import parse_list_page, parse_search_page


def load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_list_page_returns_list():
    html = load_fixture("most_wanted.html")
    results = parse_list_page(html)
    assert isinstance(results, list)
    assert len(results) > 0


def test_parse_list_page_extracts_fields():
    html = load_fixture("most_wanted.html")
    results = parse_list_page(html)
    first = results[0]
    assert "code" in first
    assert "title" in first
    assert "cover_url" in first
    assert "actresses" in first
    assert "score" in first
    assert "date" in first
    assert first["code"]


def test_parse_list_page_cover_url_format():
    html = load_fixture("most_wanted.html")
    results = parse_list_page(html)
    for item in results:
        if item["cover_url"]:
            assert item["cover_url"].startswith("http")


def test_parse_list_page_top_rated():
    html = load_fixture("top_rated.html")
    results = parse_list_page(html)
    assert isinstance(results, list)
    assert len(results) > 0


def test_parse_search_page_returns_magnets():
    html = load_fixture("search_result.html")
    search_url, magnets = parse_search_page(html)
    assert isinstance(magnets, list)
    assert isinstance(search_url, str)


def test_parse_search_page_magnets_format():
    html = load_fixture("search_result.html")
    _, magnets = parse_search_page(html)
    for m in magnets:
        assert m.startswith("magnet:")
        assert "xt=urn:btih:" in m


def test_parse_search_page_empty_on_no_results():
    html = "<html><body>No results found</body></html>"
    search_url, magnets = parse_search_page(html)
    assert magnets == []
