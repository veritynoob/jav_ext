from bs4 import BeautifulSoup
import re


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

        title_el = item.select_one("a")
        title = title_el.text.strip() if title_el else ""

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
            })
    return results
