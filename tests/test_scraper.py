import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.scraper import parse_list_page, parse_search_page, parse_search_detail_page, is_javlibrary_page, parse_detail_page


def load_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# =============================================================================
# Fixture-based parity tests — match real page structure verified by live capture
# =============================================================================
# Key finding from real pages:
#   - JavLibrary list pages (.video items): .id, .title, img, a[href], .toolbar
#     NO .score, .star, .date, .review, .cast — those are only on detail pages
#   - JavLibrary detail pages: #video_date, #video_length, #video_maker,
#     #video_label, .score, #video_cast .cast .star a[href*=vl_star], #video_jacket_img
#   - clg55.top search: li with .SearchListTitle_result_title, .Search_list_info, .Search_result_type
#   - clg55.top detail: a[href^=magnet:], .Information_title, .Information_info_wrapper .Information_l_content


class TestParseListPageMostWanted:
    """most_wanted.html — models real JavLibrary list page with 3 videos."""

    def test_returns_list(self):
        results = parse_list_page(load_fixture("most_wanted.html"))
        assert isinstance(results, list)
        assert len(results) == 3

    def test_extracts_all_keys(self):
        results = parse_list_page(load_fixture("most_wanted.html"))
        for key in ("code", "title", "cover_url", "actresses", "score", "date", "detail_url"):
            assert key in results[0], f"Missing key: {key}"

    def test_code_and_title(self):
        """Basic fields: code and clean title via .title div."""
        results = parse_list_page(load_fixture("most_wanted.html"))
        assert results[0]["code"] == "ABC-001"
        assert results[0]["title"] == "Full Featured Video"
        assert results[1]["code"] == "XYZ-002"
        assert results[2]["code"] == "NOIMG-003"
        assert results[2]["title"] == "Video With Different Image"

    def test_detail_url_is_absolute(self):
        results = parse_list_page(load_fixture("most_wanted.html"))
        assert results[0]["detail_url"].startswith("http")
        assert "javlibrary.com" in results[0]["detail_url"]

    def test_optional_fields_are_empty_defaults(self):
        """Real list pages lack .score, .star, .date — parser returns defaults."""
        results = parse_list_page(load_fixture("most_wanted.html"))
        for r in results:
            assert r["score"] == 0.0
            assert r["actresses"] == []
            assert r["date"] == ""
            assert r["cover_url"] == ""

    def test_minimal_video_falls_back_to_link_text(self):
        """Second video has no .title div — title comes from link text."""
        results = parse_list_page(load_fixture("most_wanted.html"))
        second = results[1]
        assert second["code"] == "XYZ-002"
        assert second["title"] != ""


class TestParseListPageTopRated:
    """top_rated.html — models real JavLibrary top rated list page with 2 videos."""

    def test_returns_list(self):
        results = parse_list_page(load_fixture("top_rated.html"))
        assert isinstance(results, list)
        assert len(results) == 2

    def test_code_and_title(self):
        results = parse_list_page(load_fixture("top_rated.html"))
        assert results[0]["code"] == "TOP-001"
        assert results[0]["title"] == "Top Rated Classic"
        assert results[1]["code"] == "TOP-002"
        assert results[1]["title"] == "Another Top Pick"

    def test_optional_fields_are_empty_defaults(self):
        results = parse_list_page(load_fixture("top_rated.html"))
        for r in results:
            assert r["score"] == 0.0
            assert r["actresses"] == []
            assert r["date"] == ""


class TestParseDetailPage:
    """video_detail.html — models real JavLibrary video detail page."""

    def test_extracts_all_fields(self):
        result = parse_detail_page(load_fixture("video_detail.html"))
        assert result["date"] == "2024-06-15"
        assert result["duration"] == "120"
        assert result["maker"] == "Studio X"
        assert result["label"] == "Label Y"
        # Score in real pages is "(8.52)" — parser extracts numeric part via regex
        assert result["score"] == 8.52
        assert result["actresses"] == ["Actress One", "Actress Two"]
        # Protocol-relative cover URL resolved to https
        assert result["cover_url"] == "https://pics.javlibrary.com/abc-123.jpg"


class TestIsJavlibraryPage:
    """is_javlibrary_page() detection tests."""

    def test_list_page_positive(self):
        assert is_javlibrary_page(load_fixture("most_wanted.html")) is True

    def test_top_rated_positive(self):
        assert is_javlibrary_page(load_fixture("top_rated.html")) is True

    def test_detail_page_positive(self):
        assert is_javlibrary_page(load_fixture("video_detail.html")) is True

    def test_cf_challenge_negative(self):
        assert is_javlibrary_page(load_fixture("cf_challenge.html")) is False

    def test_empty_html_negative(self):
        assert is_javlibrary_page("<html><body></body></html>") is False


class TestParseSearchPage:
    """search_result.html — models real clg55.top search results (4 items, 3 valid)."""

    def test_returns_detail_urls(self):
        html = load_fixture("search_result.html")
        search_url = "https://clg55.top/search?word=ABC-001&sort=rele"
        _search_url, results = parse_search_page(html, search_url)
        # 4 items but 1 has href without /information/ — filtered out
        assert len(results) == 3
        for url, title, download_count in results:
            assert url.startswith("https://clg55.top/information/")
            assert isinstance(title, str)
            assert len(title) > 0
            assert isinstance(download_count, str)

    def test_extracts_download_count(self):
        html = load_fixture("search_result.html")
        search_url = "https://clg55.top/search?word=ABC-001&sort=rele"
        _, results = parse_search_page(html, search_url)
        counts = [dc for _, _, dc in results]
        assert "1,234" in counts
        assert "567" in counts
        # Third result has no Search_result_type span → empty download_count
        assert "" in counts

    def test_skips_non_information_path(self):
        html = load_fixture("search_result.html")
        search_url = "https://clg55.top/search?word=ABC-001&sort=rele"
        _, results = parse_search_page(html, search_url)
        titles = [t for _, t, _ in results]
        assert "ABC-001 External Link" not in titles


class TestParseSearchDetailPage:
    """search_detail.html — models real clg55.top magnet detail page."""

    def test_extracts_magnet_and_metadata(self):
        result = parse_search_detail_page(load_fixture("search_detail.html"))
        assert result is not None
        assert result["magnet"].startswith("magnet:")
        assert "xt=urn:btih:" in result["magnet"]
        assert result["title"] == "ABC-001 HD 1080p"
        assert result["size"] == "5.2 GB"
        assert result["magnet_date"] == "2024-06-15"

    def test_no_magnet_on_empty_html(self):
        assert parse_search_detail_page("<html><body>No magnet here</body></html>") is None


# =============================================================================
# Edge case tests — inline HTML for parser robustness
# =============================================================================


class TestParseListPageEdgeCases:
    """Edge cases for parse_list_page() using inline HTML snippets."""

    def test_missing_optional_fields(self):
        """Video with no .score, .star, .date, or img — all optional fields empty."""
        html = """
        <div class="videos">
          <div class="video">
            <a href="./test.html"><div class="id">CODE-001</div><div class="title">Just a title</div></a>
          </div>
        </div>
        """
        results = parse_list_page(html)
        assert len(results) == 1
        r = results[0]
        assert r["code"] == "CODE-001"
        assert r["score"] == 0.0
        assert r["actresses"] == []
        assert r["date"] == ""
        assert r["cover_url"] == ""

    def test_non_numeric_score_returns_zero(self):
        """Score containing non-numeric text returns 0.0."""
        html = """
        <div class="videos">
          <div class="video">
            <a href="./test.html"><div class="id">C-001</div><div class="title">Test</div></a>
            <div class="score">N/A</div>
          </div>
        </div>
        """
        results = parse_list_page(html)
        assert results[0]["score"] == 0.0

    def test_score_with_parens(self):
        """Score in parentheses like real pages: (8.20) → 8.2."""
        html = """
        <div class="videos">
          <div class="video">
            <a href="./test.html"><div class="id">C-001</div><div class="title">Test</div></a>
            <div class="score">(8.20)</div>
          </div>
        </div>
        """
        results = parse_list_page(html)
        assert results[0]["score"] == 8.20

    def test_empty_videos_div(self):
        html = '<div class="videos"></div>'
        assert parse_list_page(html) == []

    def test_no_title_div_falls_back_to_link_text(self):
        html = """
        <div class="videos">
          <div class="video">
            <a href="./test.html" title="CODE-001 Title From Link">
              <div class="id">CODE-001</div>
            </a>
          </div>
        </div>
        """
        results = parse_list_page(html)
        assert results[0]["title"] != ""

    def test_detail_url_resolution(self):
        """urljoin resolves relative, protocol-relative, absolute, and query URLs."""
        html = """
        <div class="videos">
          <div class="video"><a href="./test123.html"><div class="id">A-001</div><div class="title">T</div></a></div>
          <div class="video"><a href="/cn/?v=test456"><div class="id">B-002</div><div class="title">T</div></a></div>
          <div class="video"><a href="https://www.javlibrary.com/cn/?v=test789"><div class="id">C-003</div><div class="title">T</div></a></div>
          <div class="video"><a href="?v=test000"><div class="id">D-004</div><div class="title">T</div></a></div>
        </div>
        """
        results = parse_list_page(html, "https://www.javlibrary.com/")
        assert results[0]["detail_url"] == "https://www.javlibrary.com/test123.html"
        assert results[1]["detail_url"] == "https://www.javlibrary.com/cn/?v=test456"
        assert results[2]["detail_url"] == "https://www.javlibrary.com/cn/?v=test789"
        assert results[3]["detail_url"].startswith("http")


class TestParseSearchPageEdgeCases:
    """Edge cases for parse_search_page()."""

    def test_no_valid_items(self):
        html = """
        <ul id="Search_list_wrapper">
          <li>
            <div class="SearchListTitle_list_title">
              <a href="/other/path" class="SearchListTitle_result_title">Not valid</a>
            </div>
          </li>
        </ul>
        """
        _, results = parse_search_page(html)
        assert results == []

    def test_empty_page(self):
        _, results = parse_search_page("<html><body>No results</body></html>")
        assert results == []


class TestParseSearchDetailPageEdgeCases:
    """Edge cases for parse_search_detail_page()."""

    def test_magnet_without_optional_fields(self):
        html = """
        <div id="Information_container">
          <div class="Information_magnet_wrapper">
            <div class="Information_l_content">
              <a href="magnet:?xt=urn:btih:DEADBEEF" class="Information_magnet">link</a>
            </div>
          </div>
        </div>
        """
        result = parse_search_detail_page(html)
        assert result is not None
        assert result["magnet"].startswith("magnet:")
        assert result["title"] == ""
        assert result["size"] == ""
        assert result["magnet_date"] == ""

    def test_no_magnet_link(self):
        html = """
        <div class="Information_title">Some title</div>
        <div class="Information_info_wrapper">
          <div class="Information_l_content">No magnet here</div>
        </div>
        """
        assert parse_search_detail_page(html) is None


class TestParseDetailPageEdgeCases:
    """Edge cases for parse_detail_page()."""

    def test_data_src_fallback_for_cover(self):
        html = '<img id="video_jacket_img" data-src="//pics.example.com/cover.jpg">'
        result = parse_detail_page(html)
        assert result["cover_url"] == "https://pics.example.com/cover.jpg"

    def test_src_when_no_data_src(self):
        html = '<img id="video_jacket_img" src="https://pics.example.com/cover.jpg">'
        result = parse_detail_page(html)
        assert result["cover_url"] == "https://pics.example.com/cover.jpg"

    def test_empty_fields_when_nothing_present(self):
        result = parse_detail_page("<html><body></body></html>")
        assert result["date"] == ""
        assert result["duration"] == ""
        assert result["maker"] == ""
        assert result["label"] == ""
        assert result["score"] == 0.0
        assert result["actresses"] == []
        assert result["cover_url"] == ""

    def test_maker_without_link(self):
        html = '<div id="video_maker"><table><tr><td class="text">Plain Studio</td></tr></table></div>'
        result = parse_detail_page(html)
        assert result["maker"] == "Plain Studio"

    def test_maker_with_link(self):
        html = '<div id="video_maker"><table><tr><td class="text"><a href="/m.php?id=1">Linked Studio</a></td></tr></table></div>'
        result = parse_detail_page(html)
        assert result["maker"] == "Linked Studio"

    def test_score_extraction(self):
        # Real pages use "(8.20)" format
        assert parse_detail_page('<div class="score">(9.87)</div>')["score"] == 9.87
        assert parse_detail_page('<div class="score">8.0</div>')["score"] == 8.0

    def test_duration_extraction(self):
        html = '<div id="video_length"><span class="text">90</span></div>'
        assert parse_detail_page(html)["duration"] == "90"


# =============================================================================
# Live fixture tests — use captured HTML from real sites when available
# =============================================================================


def _has_live_fixture(name):
    path = os.path.join(os.path.dirname(__file__), "fixtures", f"live_{name}.html")
    return os.path.exists(path)


@pytest.mark.live
def test_parse_list_page_live():
    if not _has_live_fixture("most_wanted"):
        pytest.skip("live fixture not available — run scripts/capture_fixtures.py")
    results = parse_list_page(load_fixture("live_most_wanted.html"))
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.live
def test_parse_detail_page_live():
    if not _has_live_fixture("video_detail"):
        pytest.skip("live fixture not available — run scripts/capture_fixtures.py")
    result = parse_detail_page(load_fixture("live_video_detail.html"))
    assert isinstance(result, dict)
    assert "date" in result
    assert result["duration"] != ""


@pytest.mark.live
def test_parse_search_page_live():
    if not _has_live_fixture("search_result"):
        pytest.skip("live fixture not available — run scripts/capture_fixtures.py")
    _, results = parse_search_page(load_fixture("live_search_result.html"))
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.live
def test_parse_search_detail_page_live():
    if not _has_live_fixture("search_detail"):
        pytest.skip("live fixture not available — run scripts/capture_fixtures.py")
    result = parse_search_detail_page(load_fixture("live_search_detail.html"))
    assert result is not None
    assert result["magnet"].startswith("magnet:")
