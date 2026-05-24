from bs4 import BeautifulSoup
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
    """Parse clg55.top search page HTML, return (search_url, list of magnet links)."""
    soup = BeautifulSoup(html, "html.parser")
    magnets = []
    for link in soup.select("a[href^='magnet:']"):
        magnet = link.get("href", "").strip()
        if magnet:
            magnets.append(magnet)
    return search_url, magnets


def parse_list_page(html):
    """Parse JavLibrary list page HTML, return list of video dicts."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    items = soup.select(".video")
    for item in items:
        code_el = item.select_one(".id")
        code = code_el.text.strip() if code_el else ""

        link_el = item.select_one("a")
        title = link_el.text.strip() if link_el else ""
        detail_url = ""
        if link_el:
            href = link_el.get("href", "")
            if href:
                if href.startswith("/"):
                    detail_url = f"https://www.javlibrary.com{href}"
                elif href.startswith("http"):
                    detail_url = href

        img_el = item.select_one("img")
        cover_url = ""
        if img_el:
            src = img_el.get("data-src") or img_el.get("src") or ""
            if src and src.startswith("//"):
                cover_url = "https:" + src
            elif src and src.startswith("http"):
                cover_url = src

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

        duration = ""
        maker = ""
        label = ""

        if code:
            results.append({
                "code": code,
                "title": title,
                "cover_url": cover_url,
                "actresses": actresses,
                "score": score,
                "date": date,
                "duration": duration,
                "maker": maker,
                "label": label,
                "detail_url": detail_url,
            })
    return results


def parse_detail_page(html):
    """Parse JavLibrary video detail page HTML, return dict of detail fields."""
    soup = BeautifulSoup(html, "html.parser")

    def _table_text(sel):
        el = soup.select_one(sel)
        if el:
            td = el.select_one("td.text")
            if td:
                return td.text.strip()
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
    for a_el in soup.select(".star a, .cast a"):
        name = a_el.text.strip()
        if name:
            actresses.append(name)

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
