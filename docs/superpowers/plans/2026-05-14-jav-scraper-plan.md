# JavLibrary 定期爬虫 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个每天从 JavLibrary 抓取榜单数据（最想要/高评价）并通过 clg55.top 补全磁力链接的爬虫，结果存入 SQLite。

**Architecture:** 纯函数解析模块 + SQLite 持久化 + cloakbrowser 浏览器自动化。Docker 环境运行和测试。所有请求走代理，页面之间加随机延迟。TDD 开发，解析逻辑用 HTML fixture 测试，数据库用文件 SQLite 测试。

**Tech Stack:** Python 3.12, cloakbrowser, sqlite3 (stdlib), pytest, Docker

---

### Task 1: 项目脚手架

**Files:**
- Create: `config.py`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 config.py**

```python
import os

JAVLIBRARY_BASE_URL = "https://www.javlibrary.com"
MOST_WANTED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_mostwanted.php"
TOP_RATED_URL = f"{JAVLIBRARY_BASE_URL}/cn/vl_toprated.php"

SEARCH_BASE_URL = "https://clg55.top"

PROXY = os.environ.get("JAV_PROXY", "http://127.0.0.1:7897")
WAIT_DELAY = int(os.environ.get("JAV_WAIT_DELAY", "40"))
COVERS_DIR = os.environ.get("JAV_COVERS_DIR", "covers")
DATA_DIR = os.environ.get("JAV_DATA_DIR", "data")
MAGNET_BACKFILL_DAYS = int(os.environ.get("JAV_MAGNET_BACKFILL_DAYS", "60"))
MAX_BACKFILL_COUNT = int(os.environ.get("JAV_MAX_BACKFILL_COUNT", "20"))
REQUEST_RETRIES = 3
PAGE_INTERVAL_MIN = 3
PAGE_INTERVAL_MAX = 5
```

- [ ] **Step 2: 创建 requirements.txt**

```
cloakbrowser
beautifulsoup4
requests
pytest
pytest-mock
requests-mock
```

- [ ] **Step 3: 创建 tests/__init__.py**

```python
```

- [ ] **Step 4: 创建 tests/conftest.py**

```python
import os
import sqlite3
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    from db import init_db
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```

- [ ] **Step 5: 确保目录存在**

```bash
mkdir -p covers data tests tests/fixtures logs
```

- [ ] **Step 6: Commit**

```bash
git add config.py requirements.txt tests/__init__.py tests/conftest.py
git commit -m "chore: add project scaffold with config and requirements"
```

---

### Task 2: Docker 环境

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-noto-cjk \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p covers data logs

ENV JAV_PROXY=http://host.docker.internal:7897
ENV JAV_WAIT_DELAY=40

CMD ["python", "main.py"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
services:
  scraper:
    build: .
    volumes:
      - ./data:/app/data
      - ./covers:/app/covers
      - ./logs:/app/logs
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - JAV_PROXY=http://host.docker.internal:7897
      - JAV_WAIT_DELAY=40
    restart: "no"

  test:
    build: .
    profiles: ["test"]
    command: python -m pytest tests/ -v
    volumes:
      - ./data:/app/data
```

- [ ] **Step 3: 创建 .dockerignore**

```
__pycache__
*.pyc
.git
data/
covers/
logs/
*.db
.env
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "chore: add Docker environment for running and testing"
```

---

### Task 3: 数据库模块 — 初始化和建表

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 编写失败测试**

```python
import os
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db_path, init_db


def test_init_db_creates_tables(db_path):
    conn = init_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    assert "videos" in tables
    assert "actresses" in tables
    assert "rankings" in tables
    assert "magnets" in tables
    conn.close()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_db.py -v
```
预期: ImportError for `db`

- [ ] **Step 3: 实现 db.py — get_db_path 和 init_db**

```python
import os
import sqlite3
from config import DATA_DIR


def get_db_path():
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, "jav.db")


def init_db(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT,
            cover_url TEXT,
            cover_path TEXT,
            date TEXT,
            duration TEXT,
            maker TEXT,
            label TEXT,
            score REAL,
            search_url TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS actresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_code TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (video_code) REFERENCES videos(code)
        );

        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_code TEXT NOT NULL,
            list_type TEXT NOT NULL CHECK(list_type IN ('most_wanted', 'top_rated')),
            rank INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (video_code) REFERENCES videos(code),
            UNIQUE(video_code, list_type)
        );

        CREATE TABLE IF NOT EXISTS magnets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_code TEXT NOT NULL,
            magnet TEXT NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (video_code) REFERENCES videos(code),
            UNIQUE(video_code, magnet)
        );
    """)
    conn.commit()
    return conn
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_db.py -v
```
预期: 1 PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add database init with tables"
```

---

### Task 4: 数据库模块 — 作品写入和排名写入

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: 编写失败测试**

```python
def test_upsert_video(conn):
    video = {
        "code": "ABC-001",
        "title": "Test Title",
        "cover_url": "http://example.com/cover.jpg",
        "date": "2026-01-01",
        "duration": "120",
        "maker": "Test Maker",
        "label": "Test Label",
        "score": 4.5,
    }
    from db import upsert_video
    upsert_video(conn, video)

    row = conn.execute("SELECT * FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row is not None
    assert row["title"] == "Test Title"
    assert row["score"] == 4.5


def test_upsert_video_updates_existing(conn):
    from db import upsert_video
    upsert_video(conn, {"code": "ABC-001", "title": "Title 1"})
    upsert_video(conn, {"code": "ABC-001", "title": "Title 2"})

    row = conn.execute("SELECT * FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["title"] == "Title 2"


def test_save_rankings(conn):
    from db import upsert_video, save_rankings
    upsert_video(conn, {"code": "ABC-001"})
    upsert_video(conn, {"code": "ABC-002"})

    entries = [
        ("ABC-001", "most_wanted", 1),
        ("ABC-002", "most_wanted", 2),
    ]
    save_rankings(conn, "most_wanted", entries)

    rows = conn.execute(
        "SELECT video_code, rank FROM rankings WHERE list_type='most_wanted' ORDER BY rank"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["video_code"] == "ABC-001"
    assert rows[1]["video_code"] == "ABC-002"


def test_save_rankings_replaces_old(conn):
    from db import upsert_video, save_rankings
    upsert_video(conn, {"code": "ABC-001"})
    save_rankings(conn, "most_wanted", [("ABC-001", "most_wanted", 1)])
    save_rankings(conn, "most_wanted", [("ABC-001", "most_wanted", 5)])

    rows = conn.execute(
        "SELECT rank FROM rankings WHERE list_type='most_wanted'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["rank"] == 5
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_db.py::test_upsert_video -v
```
预期: FAIL (no upsert_video)

- [ ] **Step 3: 实现 upsert_video, save_rankings**

```python
def upsert_video(conn, video):
    conn.execute("""
        INSERT INTO videos (code, title, cover_url, date, duration, maker, label, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            title=COALESCE(excluded.title, videos.title),
            cover_url=COALESCE(excluded.cover_url, videos.cover_url),
            date=COALESCE(excluded.date, videos.date),
            duration=COALESCE(excluded.duration, videos.duration),
            maker=COALESCE(excluded.maker, videos.maker),
            label=COALESCE(excluded.label, videos.label),
            score=COALESCE(excluded.score, videos.score),
            updated_at=datetime('now','localtime')
    """, (
        video.get("code"), video.get("title"), video.get("cover_url"),
        video.get("date"), video.get("duration"), video.get("maker"),
        video.get("label"), video.get("score"),
    ))
    conn.commit()


def save_rankings(conn, list_type, entries):
    for code, _, rank in entries:
        conn.execute("""
            INSERT INTO rankings (video_code, list_type, rank, updated_at)
            VALUES (?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(video_code, list_type) DO UPDATE SET
                rank=excluded.rank,
                updated_at=datetime('now','localtime')
        """, (code, list_type, rank))
    conn.commit()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_db.py -v
```
预期: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add video upsert and ranking save operations"
```

---

### Task 5: 数据库模块 — 演员和磁力操作 + 补漏查询

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: 编写失败测试**

```python
def test_save_actresses(conn):
    from db import upsert_video, save_actresses
    upsert_video(conn, {"code": "ABC-001"})
    save_actresses(conn, "ABC-001", ["Alice", "Bob"])

    rows = conn.execute(
        "SELECT name FROM actresses WHERE video_code='ABC-001' ORDER BY name"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"
    assert rows[1]["name"] == "Bob"


def test_save_actresses_replaces_old(conn):
    from db import upsert_video, save_actresses
    upsert_video(conn, {"code": "ABC-001"})
    save_actresses(conn, "ABC-001", ["Alice"])
    save_actresses(conn, "ABC-001", ["Charlie"])

    rows = conn.execute(
        "SELECT name FROM actresses WHERE video_code='ABC-001'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["name"] == "Charlie"


def test_save_magnets(conn):
    from db import upsert_video, save_magnets
    upsert_video(conn, {"code": "ABC-001"})
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA", "magnet:?xt=urn:btih:BBB"])

    rows = conn.execute(
        "SELECT magnet FROM magnets WHERE video_code='ABC-001' ORDER BY magnet"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["magnet"] == "magnet:?xt=urn:btih:AAA"


def test_save_magnets_ignores_duplicate(conn):
    from db import upsert_video, save_magnets
    upsert_video(conn, {"code": "ABC-001"})
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA"])
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA"])

    rows = conn.execute(
        "SELECT magnet FROM magnets WHERE video_code='ABC-001'"
    ).fetchall()
    assert len(rows) == 1


def test_get_videos_missing_magnets(conn):
    from db import upsert_video, save_magnets, get_videos_missing_magnets
    upsert_video(conn, {"code": "OLD-001"})
    upsert_video(conn, {"code": "NEW-001"})
    save_magnets(conn, "OLD-001", ["magnet:?xt=urn:btih:AAA"])

    result = get_videos_missing_magnets(conn, days=60, limit=20)
    assert len(result) == 1
    assert result[0] == "NEW-001"


def test_update_video_search_url(conn):
    from db import upsert_video, update_video_search_url
    upsert_video(conn, {"code": "ABC-001"})
    update_video_search_url(conn, "ABC-001", "https://clg55.top/search/ABC-001")

    row = conn.execute("SELECT search_url FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["search_url"] == "https://clg55.top/search/ABC-001"


def test_update_video_cover_path(conn):
    from db import upsert_video, update_video_cover_path
    upsert_video(conn, {"code": "ABC-001"})
    update_video_cover_path(conn, "ABC-001", "covers/ABC-001.jpg")

    row = conn.execute("SELECT cover_path FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["cover_path"] == "covers/ABC-001.jpg"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_db.py::test_save_actresses -v
```
预期: FAIL

- [ ] **Step 3: 实现函数**

```python
def save_actresses(conn, video_code, names):
    conn.execute("DELETE FROM actresses WHERE video_code=?", (video_code,))
    for name in names:
        if name.strip():
            conn.execute(
                "INSERT INTO actresses (video_code, name) VALUES (?, ?)",
                (video_code, name.strip())
            )
    conn.commit()


def save_magnets(conn, video_code, magnets):
    for magnet in magnets:
        if magnet.strip():
            conn.execute(
                "INSERT OR IGNORE INTO magnets (video_code, magnet, source) VALUES (?, ?, ?)",
                (video_code, magnet.strip(), "clg55")
            )
    conn.commit()


def get_videos_missing_magnets(conn, days=60, limit=20):
    rows = conn.execute("""
        SELECT code FROM videos
        WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)
        AND created_at >= datetime('now', 'localtime', '-' || ? || ' days')
        ORDER BY created_at DESC
        LIMIT ?
    """, (days, limit)).fetchall()
    return [row["code"] for row in rows]


def update_video_search_url(conn, code, search_url):
    conn.execute(
        "UPDATE videos SET search_url=?, updated_at=datetime('now','localtime') WHERE code=?",
        (search_url, code)
    )
    conn.commit()


def update_video_cover_path(conn, code, cover_path):
    conn.execute(
        "UPDATE videos SET cover_path=?, updated_at=datetime('now','localtime') WHERE code=?",
        (cover_path, code)
    )
    conn.commit()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_db.py -v
```
预期: all PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add actress/magnet save, missing-magnet query, search_url/cover_path update"
```

---

### Task 6: 列表页解析 — JavLibrary 榜单页

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`
- Create: `tests/fixtures/most_wanted.html`
- Create: `tests/fixtures/top_rated.html`

> **依赖:** beautifulsoup4 已在 Task 1 的 requirements.txt 中声明。

- [ ] **Step 1: 创建 HTML fixture**

用 cloakbrowser 访问 JavLibrary 两个榜单页，保存完整 HTML 到 fixtures 目录。执行时使用以下临时脚本：

```python
# save_fixtures.py (临时)
from cloakbrowser import launch
import time
browser = launch(proxy="http://127.0.0.1:7897", humanize=True, headless=False)
page = browser.new_page()
page.goto("https://www.javlibrary.com/cn/vl_mostwanted.php")
time.sleep(40)
with open("tests/fixtures/most_wanted.html", "w", encoding="utf-8") as f:
    f.write(page.content())
page.close()

page = browser.new_page()
page.goto("https://www.javlibrary.com/cn/vl_toprated.php")
time.sleep(40)
with open("tests/fixtures/top_rated.html", "w", encoding="utf-8") as f:
    f.write(page.content())
page.close()
browser.close()
```

- [ ] **Step 2: 编写失败测试 — parse_list_page**

```python
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import parse_list_page


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
```

- [ ] **Step 3: 运行测试**

```bash
python -m pytest tests/test_scraper.py -v
```
预期: FAIL (no parse_list_page)

- [ ] **Step 4: 实现 parse_list_page**

> **注意:** 下列 CSS 选择器是占位值，实现时需根据 fixture 中的实际 HTML 结构调整。查看 fixture 确认准确的类名。

```python
from bs4 import BeautifulSoup
import re


def parse_list_page(html):
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
```

- [ ] **Step 5: 根据 fixture 调整选择器**

打开 fixture HTML，确认实际的 DOM 结构，更新 CSS 选择器直到测试通过。

- [ ] **Step 6: 运行测试验证通过**

```bash
python -m pytest tests/test_scraper.py -v
```
预期: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add scraper.py tests/test_scraper.py tests/fixtures/
git commit -m "feat: add JavLibrary list page parser"
```

---

### Task 7: 磁力搜索页解析 — clg55.top

**Files:**
- Modify: `scraper.py`
- Modify: `tests/test_scraper.py`
- Create: `tests/fixtures/search_result.html`

- [ ] **Step 1: 创建搜索页 fixture**

用 cloakbrowser 访问 `https://clg55.top/search/` + 一个已知番号，保存 HTML 到 `tests/fixtures/search_result.html`。

- [ ] **Step 2: 编写失败测试**

```python
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
```

- [ ] **Step 3: 运行测试验证失败**

```bash
python -m pytest tests/test_scraper.py::test_parse_search_page_returns_magnets -v
```
预期: FAIL

- [ ] **Step 4: 实现 parse_search_page**

```python
def parse_search_page(html, search_url=""):
    soup = BeautifulSoup(html, "html.parser")
    magnets = []
    for link in soup.select("a[href^='magnet:']"):
        magnet = link.get("href", "").strip()
        if magnet:
            magnets.append(magnet)
    return search_url, magnets
```

> 根据 fixture 实际结构调整 `a[href^='magnet:']` 选择器。

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_scraper.py -v
```
预期: 7 PASS

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py tests/fixtures/search_result.html
git commit -m "feat: add clg55 search page parser"
```

---

### Task 8: 封面下载

**Files:**
- Create: `downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: 编写失败测试**

```python
import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader import download_cover


def test_download_cover_returns_path(tmp_path, requests_mock):
    code = "ABC-001"
    url = "http://example.com/cover.jpg"
    requests_mock.get(url, content=b"fake-image-data")

    result = download_cover(code, url, str(tmp_path))
    assert result is not None
    assert result.endswith("ABC-001.jpg")


def test_download_cover_saves_file(tmp_path, requests_mock):
    code = "ABC-001"
    url = "http://example.com/cover.jpg"
    requests_mock.get(url, content=b"fake-image-data")

    result = download_cover(code, url, str(tmp_path))
    assert os.path.exists(result)
    with open(result, "rb") as f:
        assert f.read() == b"fake-image-data"


def test_download_cover_returns_none_on_failure(tmp_path):
    code = "ABC-001"
    url = "http://invalid-url-that-does-not-exist.xyz/cover.jpg"
    result = download_cover(code, url, str(tmp_path))
    assert result is None


def test_download_cover_empty_url(tmp_path):
    result = download_cover("ABC-001", "", str(tmp_path))
    assert result is None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_downloader.py -v
```
预期: FAIL (no download_cover)

- [ ] **Step 3: 实现 download_cover**

```python
import os
import requests


def download_cover(code, url, covers_dir="covers"):
    if not url:
        return None
    os.makedirs(covers_dir, exist_ok=True)
    ext = ".jpg"
    if url.lower().endswith((".png", ".gif", ".webp")):
        ext = os.path.splitext(url)[1]
    filepath = os.path.join(covers_dir, f"{code}{ext}")
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    except Exception:
        return None
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_downloader.py -v
```
预期: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add downloader.py tests/test_downloader.py
git commit -m "feat: add cover image downloader"
```

---

### Task 9: 主入口 — 流程编排

**Files:**
- Create: `main.py`

`main.py` 整合所有模块，依赖 cloakbrowser 和真实网络。

- [ ] **Step 1: 实现 main.py**

```python
import logging
import random
import time
import sys
from cloakbrowser import launch
from config import (
    MOST_WANTED_URL, TOP_RATED_URL, SEARCH_BASE_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, REQUEST_RETRIES,
    PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX,
)
from scraper import parse_list_page, parse_search_page
from db import (
    init_db, upsert_video, save_actresses, save_magnets,
    save_rankings, get_videos_missing_magnets, update_video_search_url,
    update_video_cover_path,
)
from downloader import download_cover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def random_delay():
    delay = random.uniform(PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX)
    logger.info(f"Sleeping {delay:.1f}s...")
    time.sleep(delay)


def scrape_list(browser, url, list_type):
    logger.info(f"Fetching {list_type}: {url}")
    for attempt in range(REQUEST_RETRIES):
        try:
            page = browser.new_page()
            page.goto(url)
            logger.info(f"Waiting {WAIT_DELAY}s for page to load...")
            time.sleep(WAIT_DELAY)
            html = page.content()
            page.close()
            items = parse_list_page(html)
            logger.info(f"Parsed {len(items)} items from {list_type}")
            return items
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{REQUEST_RETRIES} failed for {list_type}: {e}")
            if attempt < REQUEST_RETRIES - 1:
                random_delay()
    logger.error(f"All attempts failed for {list_type}")
    return []


def scrape_magnets(browser, code):
    search_url = f"{SEARCH_BASE_URL}/search/{code}"
    logger.info(f"Searching magnets for {code}")
    for attempt in range(REQUEST_RETRIES):
        try:
            page = browser.new_page()
            page.goto(search_url)
            time.sleep(random.uniform(3, 5))
            html = page.content()
            page.close()
            _, magnets = parse_search_page(html, search_url)
            logger.info(f"Found {len(magnets)} magnets for {code}")
            return search_url, magnets
        except Exception as e:
            logger.warning(f"Magnet attempt {attempt+1}/{REQUEST_RETRIES} failed for {code}: {e}")
            if attempt < REQUEST_RETRIES - 1:
                random_delay()
    return search_url, []


def main():
    logger.info("Starting JavLibrary scraper")
    browser = None
    try:
        browser = launch(proxy=PROXY, humanize=True, headless=False)
    except Exception as e:
        logger.error(f"Failed to launch browser: {e}")
        sys.exit(1)

    try:
        conn = init_db()

        # 1. 抓取榜单页
        all_items = {}
        for url, list_type in [(MOST_WANTED_URL, "most_wanted"), (TOP_RATED_URL, "top_rated")]:
            items = scrape_list(browser, url, list_type)
            for idx, item in enumerate(items):
                code = item["code"]
                if code not in all_items:
                    all_items[code] = item

                upsert_video(conn, item)
                save_actresses(conn, code, item.get("actresses", []))
                logger.info(f"Saved {code}: {item.get('title','')[:40]}")

                if item.get("cover_url"):
                    path = download_cover(code, item["cover_url"], COVERS_DIR)
                    if path:
                        update_video_cover_path(conn, code, path)
                        logger.info(f"Cover saved: {path}")

            ranking_entries = [(item["code"], list_type, idx + 1) for idx, item in enumerate(items)]
            save_rankings(conn, list_type, ranking_entries)

            random_delay()

        # 2. 为新番号搜索磁力链接
        logger.info("Fetching magnets for new videos...")
        for code in all_items:
            search_url, magnets = scrape_magnets(browser, code)
            if search_url:
                update_video_search_url(conn, code, search_url)
            if magnets:
                save_magnets(conn, code, magnets)
            random_delay()

        # 3. 补漏旧的缺失磁力链接
        logger.info(f"Backfilling magnets (within {MAGNET_BACKFILL_DAYS} days)...")
        missing_codes = get_videos_missing_magnets(conn, days=MAGNET_BACKFILL_DAYS, limit=MAX_BACKFILL_COUNT)
        logger.info(f"Found {len(missing_codes)} videos needing magnet backfill")
        for code in missing_codes:
            search_url, magnets = scrape_magnets(browser, code)
            if search_url:
                update_video_search_url(conn, code, search_url)
            if magnets:
                save_magnets(conn, code, magnets)
            random_delay()

        logger.info("Scrape complete")
        conn.close()
    finally:
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证语法正确**

```bash
python -m py_compile main.py
```
预期: 无输出

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry with full scrape orchestration"
```

---

### Task 10: 最终验证 — Docker 内测试通过

- [ ] **Step 1: 构建 Docker 镜像**

```bash
docker compose build
```
预期: 构建成功

- [ ] **Step 2: 运行全部测试**

```bash
docker compose run --rm test
```
预期: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: all tests pass in Docker"
```

---

### 完成后的手动验证

Docker 环境验证流程：

1. **构建镜像:** `docker compose build`
2. **运行一次完整抓取:** `docker compose run --rm scraper`
3. **检查数据输出:** `sqlite3 data/jav.db "SELECT code, title FROM videos LIMIT 5;"`
4. **检查封面:** `ls covers/`
5. **检查磁力:** `sqlite3 data/jav.db "SELECT video_code, COUNT(*) FROM magnets GROUP BY video_code;"`

一切正常后，配置 cron（宿主机）:

```
0 3 * * * cd /home/wangj/playground/jav_ext && docker compose run --rm scraper >> logs/cron.log 2>&1
```
