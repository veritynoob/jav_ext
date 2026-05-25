from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re


def is_javlibrary_page(html):
    """Check if HTML is a real JavLibrary content page (not a challenge/error page)."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.select(".video .id"):
        return True
    if soup.select("a[href^='magnet:']"):
        return True
    if soup.select("#video_date"):
        return True
    if soup.select("#video_id"):
        return True
    return False


def parse_search_page(html, search_url=""):
    """Parse clg55.top search results page, return (search_url, list of (detail_url, title, download_count) tuples)."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for item in soup.select("li"):
        link = item.select_one("a.SearchListTitle_result_title[href]")
        if not link:
            continue
        href = link.get("href", "").strip()
        if not href.startswith("/information/"):
            continue
        title = link.text.strip()
        download_count = ""
        info_el = item.select_one(".Search_list_info")
        if info_el:
            hits_el = info_el.select_one("span.Search_result_type")
            if hits_el:
                hits_match = re.search(r"([\d,]+)", hits_el.get_text())
                if hits_match:
                    download_count = hits_match.group(1)
        results.append((urljoin(search_url, href), title, download_count))
    return search_url, results


def parse_search_detail_page(html):
    """Parse clg55.top magnet detail page, return dict with magnet + metadata or None."""
    soup = BeautifulSoup(html, "html.parser")
    magnet_el = soup.select_one("a[href^='magnet:']")
    if not magnet_el:
        return None

    magnet = magnet_el.get("href", "").strip()

    title = ""
    title_el = soup.select_one(".Information_title")
    if title_el:
        title = title_el.text.strip()

    size = ""
    magnet_date = ""
    info_el = soup.select_one(".Information_info_wrapper .Information_l_content")
    if info_el:
        text = info_el.get_text()
        size_match = re.search(r"文件大小[：:]\s*(.+)", text)
        if size_match:
            size = size_match.group(1).strip()
        date_match = re.search(r"收录时间[：:]\s*(.+)", text)
        if date_match:
            magnet_date = date_match.group(1).strip()

    return {
        "magnet": magnet,
        "title": title,
        "size": size,
        "magnet_date": magnet_date,
    }


BASE_URL = "https://www.javlibrary.com"


def parse_list_page(html, page_url=None):
    """Parse JavLibrary list page HTML, return list of video dicts.

    Args:
        html: Raw HTML of the list page.
        page_url: URL of the list page, used to resolve relative detail URLs.
    """
    if page_url is None:
        page_url = BASE_URL + "/cn/"
    soup = BeautifulSoup(html, "html.parser")
    results = []
    items = soup.select(".video")
    for item in items:
        code_el = item.select_one(".id")
        code = code_el.text.strip() if code_el else ""

        # Title: prefer .title div (clean, no code prefix), fallback to link text
        title_el = item.select_one(".title")
        if title_el:
            title = title_el.text.strip()
        else:
            title = ""
        if not title:
            link_el = item.select_one("a[href]")
            if link_el:
                title = link_el.text.strip()

        # Detail URL: use urljoin to handle ./path.html, ?v=xxx, /path, https://...
        detail_url = ""
        link_el = item.select_one("a[href]")
        if link_el:
            href = link_el.get("href", "")
            if href:
                detail_url = urljoin(page_url, href)

        cover_url = ""

        score_el = item.select_one(".score, .review")
        score = 0.0
        if score_el:
            score_text = score_el.text.strip()
            score_match = re.search(r"[\d.]+", score_text)
            if score_match:
                score = float(score_match.group())

        actresses = []
        actress_els = item.select(".star a, .actress a, .cast a")
        for a_el in actress_els:
            name = a_el.text.strip()
            if name:
                actresses.append(name)

        date_el = item.select_one(".date")
        date = date_el.text.strip() if date_el else ""

        if code:
            results.append({
                "code": code,
                "title": title,
                "cover_url": cover_url,
                "actresses": actresses,
                "score": score,
                "date": date,
                "duration": "",
                "maker": "",
                "label": "",
                "detail_url": detail_url,
            })
    return results


def parse_detail_page(html):
    """Parse JavLibrary video detail page HTML, return dict of detail fields."""
    soup = BeautifulSoup(html, "html.parser")

    def _table_text(sel):
        el = soup.select_one(sel)
        if el:
            text_el = el.select_one(".text")
            if text_el:
                return text_el.text.strip()
        return ""

    date = _table_text("#video_date")
    duration = _table_text("#video_length")

    maker = ""
    maker_el = soup.select_one("#video_maker td.text a, #video_maker td.text")
    if maker_el:
        maker = maker_el.text.strip()

    label = ""
    label_el = soup.select_one("#video_label td.text a, #video_label td.text")
    if label_el:
        label = label_el.text.strip()

    score = 0.0
    score_el = soup.select_one(".score")
    if score_el:
        score_match = re.search(r"[\d.]+", score_el.text)
        if score_match:
            score = float(score_match.group())

    actresses = []
    for a_el in soup.select("#video_cast .cast .star a[href*=vl_star]"):
        name = a_el.text.strip()
        if not name:
            continue
        href = a_el.get("href", "")
        m = re.search(r's=(\w+)', href)
        actress_id = m.group(1) if m else ""
        actresses.append((name, actress_id))

    cover_url = ""
    img_el = soup.select_one("#video_jacket_img")
    if img_el:
        src = img_el.get("data-src") or img_el.get("src") or ""
        if src.startswith("//"):
            cover_url = "https:" + src
        elif src.startswith("http"):
            cover_url = src

    return {
        "date": date,
        "duration": duration,
        "maker": maker,
        "label": label,
        "score": score,
        "actresses": actresses,
        "cover_url": cover_url,
    }
