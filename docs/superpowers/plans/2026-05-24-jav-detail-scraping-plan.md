# JAV Detail Page Scraping & UI Rework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add detail page scraping to fetch full video metadata, rework video list as a grid, and simplify the sidebar.

**Architecture:** `parse_detail_page()` extracts metadata from JavLibrary detail pages. `main.py`'s scrape loop becomes: fetch list page → for each item, fetch detail page → merge and upsert. No magnet scraping in the main flow. UI switches to CSS grid cards, sidebar drops Dashboard/Magnets links.

**Tech Stack:** Python 3.11, BeautifulSoup4, FastAPI, Jinja2, HTMX, Pico.css

---

### Task 1: Update config — replace interval constants

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Replace PAGE_INTERVAL_MIN/MAX with WAIT_MIN/MAX**

Replace lines 16-17:

```python
PAGE_INTERVAL_MIN = 3
PAGE_INTERVAL_MAX = 5
```

with:

```python
WAIT_MIN = int(os.environ.get("JAV_WAIT_MIN", "5"))
WAIT_MAX = int(os.environ.get("JAV_WAIT_MAX", "15"))
```

- [ ] **Step 2: Verify config imports still work**

Run: `./myenv/bin/python -c "from src.config import WAIT_MIN, WAIT_MAX; print(WAIT_MIN, WAIT_MAX)"`
Expected: `5 15`

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "refactor: replace PAGE_INTERVAL_MIN/MAX with WAIT_MIN/MAX (5-15s default)"
```

---

### Task 2: Add `parse_detail_page()` to scraper

**Files:**
- Create: `tests/fixtures/video_detail.html` (test fixture)
- Modify: `src/scraper.py`

- [ ] **Step 1: Create a detail page HTML fixture**

Create `tests/fixtures/video_detail.html`:

```html
<!DOCTYPE html>
<html>
<body>
<div id="video_date"><table><tr><td class="text">2024-06-15</td></tr></table></div>
<div id="video_length"><table><tr><td class="text">120 min</td></tr></table></div>
<div id="video_maker"><table><tr><td class="text"><a href="/cn/maker.php?id=abc">Studio X</a></td></tr></table></div>
<div id="video_label"><table><tr><td class="text"><a href="/cn/label.php?id=xyz">Label Y</a></td></tr></table></div>
<div class="score">8.52</div>
<span class="star"><a href="/cn/star.php?s=aaa">Actress One</a></span>
<span class="star"><a href="/cn/star.php?s=bbb">Actress Two</a></span>
<img id="video_jacket_img" src="//pics.javlibrary.com/abc-123.jpg">
</body>
</html>
```

- [ ] **Step 2: Write the failing test**

Add to the existing test file or create `tests/test_scraper.py` if it doesn't exist. Add:

```python
from src.scraper import parse_detail_page


def test_parse_detail_page():
    with open("tests/fixtures/video_detail.html") as f:
        html = f.read()
    result = parse_detail_page(html)

    assert result["date"] == "2024-06-15"
    assert result["duration"] == "120 min"
    assert result["maker"] == "Studio X"
    assert result["label"] == "Label Y"
    assert result["score"] == 8.52
    assert result["actresses"] == ["Actress One", "Actress Two"]
    assert result["cover_url"] == "https://pics.javlibrary.com/abc-123.jpg"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./myenv/bin/pytest tests/test_scraper.py::test_parse_detail_page -v`
Expected: FAIL with "parse_detail_page not defined"

- [ ] **Step 4: Implement `parse_detail_page()` in scraper.py**

Add to `src/scraper.py` after `parse_list_page`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./myenv/bin/pytest tests/test_scraper.py::test_parse_detail_page -v`
Expected: PASS

- [ ] **Step 6: Update `parse_list_page()` to extract detail_url**

In `src/scraper.py`, inside the `for item in items` loop, after `title_el = item.select_one("a")`, add extraction of the href:

```python
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
```

And add `"detail_url": detail_url` to the result dict.

Run the existing list page test to verify it still passes:

Run: `./myenv/bin/pytest tests/test_scraper.py -v`
Expected: All existing tests pass, new detail_url field appears in parsed items

- [ ] **Step 7: Verify is_javlibrary_page recognizes detail pages**

The function checks for `.video .id` or `a[href^='magnet:']`. Detail pages likely have neither. Add a check for detail page indicators:

In `is_javlibrary_page()`, add:

```python
    if soup.select("#video_date"):
        return True
    if soup.select("#video_id"):
        return True
```

Update the test:

```python
def test_is_javlibrary_page_detail():
    with open("tests/fixtures/video_detail.html") as f:
        html = f.read()
    assert is_javlibrary_page(html) is True
```

Run: `./myenv/bin/pytest tests/test_scraper.py::test_is_javlibrary_page_detail -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/scraper.py tests/fixtures/video_detail.html tests/test_scraper.py
git commit -m "feat: add parse_detail_page() and extract detail_url from list pages"
```

---

### Task 3: Rework main.py scraping flow

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Update imports in main.py**

Replace:

```python
from src.config import (
    MOST_WANTED_URL, TOP_RATED_URL, SEARCH_BASE_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, REQUEST_RETRIES,
    PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX,
)
from src.scraper import parse_list_page, parse_search_page, is_javlibrary_page
from src.db import (
    init_db, upsert_video, save_actresses, save_magnets,
    save_rankings, get_videos_missing_magnets, update_video_search_url,
    update_video_cover_path,
)
```

with:

```python
from src.config import (
    MOST_WANTED_URL, TOP_RATED_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, REQUEST_RETRIES, WAIT_MIN, WAIT_MAX,
)
from src.scraper import parse_list_page, parse_detail_page, is_javlibrary_page
from src.db import (
    init_db, upsert_video, save_actresses,
    save_rankings, update_video_cover_path,
)
```

- [ ] **Step 2: Update `random_delay()`**

Replace:

```python
def random_delay():
    delay = random.uniform(PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX)
    logger.info(f"Sleeping {delay:.1f}s...")
    time.sleep(delay)
```

with:

```python
def random_delay():
    delay = random.uniform(WAIT_MIN, WAIT_MAX)
    logger.info(f"Sleeping {delay:.1f}s...")
    time.sleep(delay)
```

- [ ] **Step 3: Add `scrape_detail()` function**

Add after `scrape_list()`:

```python
def scrape_detail(code, detail_url):
    """Fetch and parse a single video detail page. Returns dict or None on failure."""
    logger.info(f"Fetching detail for {code}: {detail_url}")
    try:
        html = load_with_cf_bypass(detail_url, proxy=PROXY, wait=WAIT_DELAY, timeout=60, headless=True)
        if html is None:
            raise Exception("Failed to load detail page past Cloudflare")
        if not is_javlibrary_page(html):
            raise Exception("Loaded page is not JavLibrary content")
        detail = parse_detail_page(html)
        logger.info(f"Detail for {code}: score={detail.get('score')}, date={detail.get('date')}")
        return detail
    except Exception as e:
        logger.warning(f"Detail fetch failed for {code}: {e}")
        return None


MAX_CONSECUTIVE_FAILURES = 5


def scrape_all():
    """Main entry: scrape list pages, then detail page for each video."""
    logger.info("Starting JavLibrary scraper (list + detail mode)")
    conn = init_db()
    stats = {"succeeded": 0, "skipped": 0, "failed": 0}
    consecutive_failures = 0

    try:
        all_items = {}
        for url, list_type in [(MOST_WANTED_URL, "most_wanted"), (TOP_RATED_URL, "top_rated")]:
            items = scrape_list(url, list_type)
            ranking_entries = []
            for idx, item in enumerate(items):
                code = item["code"]
                if code not in all_items:
                    all_items[code] = item
                ranking_entries.append((code, list_type, idx + 1))
            save_rankings(conn, list_type, ranking_entries)

        logger.info(f"Total unique videos from lists: {len(all_items)}")

        for code, item in list(all_items.items()):
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.error(f"Aborting after {MAX_CONSECUTIVE_FAILURES} consecutive failures")
                break

            detail_url = item.get("detail_url", "")
            if not detail_url:
                logger.warning(f"No detail_url for {code}, skipping")
                stats["skipped"] += 1
                continue

            random_delay()
            detail = scrape_detail(code, detail_url)
            if detail is None:
                stats["failed"] += 1
                consecutive_failures += 1
                continue

            consecutive_failures = 0
            stats["succeeded"] += 1

            # Merge: detail overrides list (higher quality cover_url)
            merged = {**item, **detail}
            upsert_video(conn, merged)
            save_actresses(conn, code, merged.get("actresses", []))
            logger.info(f"Saved {code}: {merged.get('title','')[:40]}")

            if merged.get("cover_url"):
                path = download_cover(code, merged["cover_url"], COVERS_DIR)
                if path:
                    update_video_cover_path(conn, code, path)
                    logger.info(f"Cover saved: {path}")

        logger.info(f"Scrape complete. Succeeded={stats['succeeded']}, Skipped={stats['skipped']}, Failed={stats['failed']}")
    finally:
        conn.close()
```

- [ ] **Step 4: Replace `main()` entry point**

Replace the entire `main()` function with:

```python
def main():
    scrape_all()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Remove dead functions**

Delete `scrape_magnets()` entirely (magnet search is now separate, not part of the main flow).

- [ ] **Step 6: Verify imports resolve**

Run: `./myenv/bin/python -c "from src.main import scrape_all, scrape_detail, scrape_list; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add src/main.py
git commit -m "feat: rework scrape flow to include detail page fetching per video"
```

---

### Task 4: Simplify sidebar — remove Dashboard and Magnets links

**Files:**
- Modify: `src/web/templates/base.html`

- [ ] **Step 1: Remove Dashboard and Magnets links from sidebar**

In `src/web/templates/base.html`, replace:

```html
            <nav>
                <a href="/" hx-get="/" hx-target="#main" hx-push-url="true">Dashboard</a>
                <a href="/videos" hx-get="/videos" hx-target="#main" hx-push-url="true">Videos</a>
                <a href="/actresses" hx-get="/actresses" hx-target="#main" hx-push-url="true">Actresses</a>
                <a href="/magnets" hx-get="/magnets" hx-target="#main" hx-push-url="true">Magnets</a>
                <a href="/tasks" hx-get="/tasks" hx-target="#main" hx-push-url="true">Tasks</a>
            </nav>
```

with:

```html
            <nav>
                <a href="/videos" hx-get="/videos" hx-target="#main" hx-push-url="true">Videos</a>
                <a href="/actresses" hx-get="/actresses" hx-target="#main" hx-push-url="true">Actresses</a>
                <a href="/tasks" hx-get="/tasks" hx-target="#main" hx-push-url="true">Tasks</a>
            </nav>
```

- [ ] **Step 2: Verify visually**

Run the app and confirm sidebar only shows: JAV Panel (home), Videos, Actresses, Tasks, Logout.

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/base.html
git commit -m "ui: remove Dashboard and Magnets links from sidebar navigation"
```

---

### Task 5: Video list — switch to CSS grid layout

**Files:**
- Modify: `src/web/templates/videos_partial.html`
- Modify: `src/web/templates/base.html` (add grid styles)

- [ ] **Step 1: Add grid card styles to base.html**

Add to the `<style>` block in `base.html` after the existing styles:

```css
        .video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
        .video-card { border: 1px solid var(--pico-muted-border-color); border-radius: 8px; overflow: hidden; }
        .video-card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
        .video-card .info { padding: 0.5rem; }
        .video-card .code { font-weight: bold; font-size: 0.9rem; }
        .video-card .title { font-size: 0.8rem; color: var(--pico-muted-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .video-card .meta { font-size: 0.8rem; margin-top: 0.25rem; display: flex; justify-content: space-between; }
```

- [ ] **Step 2: Rewrite videos_partial.html as grid**

Replace the entire contents of `src/web/templates/videos_partial.html`:

```html
<div id="video-table">
<div class="video-grid">
{% for v in videos %}
<div class="video-card">
    <a href="/videos/{{ v.code }}">
        {% if v.cover_url %}
        <img src="{{ v.cover_url }}" alt="{{ v.code }}" loading="lazy">
        {% else %}
        <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 2 3'/>" alt="no cover">
        {% endif %}
    </a>
    <div class="info">
        <div class="code"><a href="/videos/{{ v.code }}">{{ v.code }}</a></div>
        <div class="title">{{ v.title[:60] if v.title else '' }}</div>
        <div class="meta">
            <span>{% if v.score %}★ {{ v.score }}{% endif %}</span>
            <span>{% if v.date %}{{ v.date }}{% endif %}</span>
        </div>
    </div>
</div>
{% endfor %}
</div>

{% if total_pages > 1 %}
<nav style="margin-top:1rem;">
    <ul style="display:flex; gap:0.5rem; list-style:none; padding:0;">
    {% for p in range(1, total_pages + 1) %}
        <li>
            <a {% if p == page %}class="active"{% endif %}
               hx-get="/videos?q={{ q }}&sort={{ sort }}&order={{ order }}&list_type={{ list_type }}&page={{ p }}"
               hx-target="#main" hx-push-url="true"
               href="/videos?q={{ q }}&sort={{ sort }}&order={{ order }}&list_type={{ list_type }}&page={{ p }}"
               role="button" style="padding:0.3rem 0.6rem;">{{ p }}</a>
        </li>
    {% endfor %}
    </ul>
</nav>
{% endif %}
</div>
```

- [ ] **Step 3: Verify visually**

Run the app and navigate to /videos. Confirm cards render in a responsive grid.

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/videos_partial.html src/web/templates/base.html
git commit -m "ui: switch video list from table to responsive CSS grid cards"
```

---

### Task 6: Remove magnets route registration

**Files:**
- Modify: `src/web/routes/__init__.py`

- [ ] **Step 1: Remove magnets router**

In `src/web/routes/__init__.py`, remove these two lines:

```python
    from src.web.routes.magnets import router as magnets_router
    app.include_router(magnets_router)
```

- [ ] **Step 2: Verify app still starts**

Run: `./myenv/bin/python -c "from src.web.app import app; print('OK')"`
Expected: `OK` (no import error for magnets module)

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/__init__.py
git commit -m "ui: remove magnets route from web panel"
```

---

### Task 7: Add empty state to actresses page

**Files:**
- Modify: `src/web/templates/actresses.html`

- [ ] **Step 1: Add empty state and fix hx-target**

In `src/web/templates/actresses.html`, replace the `<tbody>` content:

```html
    <tbody>
    {% for a in actresses %}
    <tr>
        <td>{{ a.name }}</td>
        <td>{{ a.video_count }}</td>
        <td>
            <button hx-get="/actresses/{{ a.name|urlencode }}/videos"
                    hx-target="next tr" hx-swap="afterend"
                    hx-trigger="click once">Show videos</button>
        </td>
    </tr>
    {% else %}
    <tr><td colspan="3">No actresses found. Scrape some videos first.</td></tr>
    {% endfor %}
    </tbody>
```

- [ ] **Step 2: Verify visually**

Run the app and navigate to /actresses with an empty database. Confirm "No actresses found" message appears.

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/actresses.html
git commit -m "fix: add empty state and urlencode to actresses page"
```

---

### Task 8: Final integration test

**Files:**
- Modify: `tests/` (add integration test)

- [ ] **Step 1: Write integration test for the web panel**

Add to the test file that tests routes:

```python
def test_videos_page_returns_grid():
    from fastapi.testclient import TestClient
    from src.web.app import app
    client = TestClient(app)
    # Login first
    client.post("/login", data={"password": "admin"})
    resp = client.get("/videos")
    assert resp.status_code == 200
    assert "video-grid" in resp.text
    assert "video-card" in resp.text


def test_actresses_page_shows_empty_state():
    from fastapi.testclient import TestClient
    from src.web.app import app
    client = TestClient(app)
    client.post("/login", data={"password": "admin"})
    resp = client.get("/actresses")
    assert resp.status_code == 200
    assert "No actresses found" in resp.text


def test_magnets_route_removed():
    from fastapi.testclient import TestClient
    from src.web.app import app
    client = TestClient(app)
    client.post("/login", data={"password": "admin"})
    resp = client.get("/magnets")
    assert resp.status_code == 404


def test_sidebar_no_dashboard_link():
    from fastapi.testclient import TestClient
    from src.web.app import app
    client = TestClient(app)
    client.post("/login", data={"password": "admin"})
    resp = client.get("/videos")
    assert "Dashboard" not in resp.text
    assert "Magnets" not in resp.text
```

- [ ] **Step 2: Run integration tests**

Run: `./myenv/bin/pytest tests/ -v -k "test_videos_page_returns_grid or test_actresses_page_shows_empty_state or test_magnets_route_removed or test_sidebar_no_dashboard_link"`
Expected: 4 PASS

- [ ] **Step 3: Run full test suite**

Run: `./myenv/bin/pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add integration tests for grid layout, empty state, sidebar and route changes"
```
