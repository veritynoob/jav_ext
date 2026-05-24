# JAV Web Management Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + Jinja2 + HTMX web management panel for the JavLibrary scraper data.

**Architecture:** FastAPI serves Jinja2 templates with HTMX for partial page updates. A session-based auth middleware protects all routes. The existing `db.py` module provides all data access — no schema changes needed. Background tasks run the existing scraper logic via threading with in-memory status tracking.

**Tech Stack:** FastAPI, Jinja2, HTMX (CDN), Pico.css (CDN), Starlette SessionMiddleware, python-multipart

---

### Task 1: Move existing code into src/ directory

**Files:**
- Create: `src/__init__.py`
- Move (git mv): `main.py`, `scraper.py`, `db.py`, `config.py`, `downloader.py`, `page_utils.py` → `src/`
- Modify: `tests/conftest.py`, `tests/test_db.py`, `tests/test_scraper.py`, `tests/test_page_utils.py`, `tests/test_downloader.py`

- [ ] **Step 1: Create src/__init__.py and move source files**

```bash
mkdir -p src
touch src/__init__.py
git mv main.py src/main.py
git mv scraper.py src/scraper.py
git mv db.py src/db.py
git mv config.py src/config.py
git mv downloader.py src/downloader.py
git mv page_utils.py src/page_utils.py
```

- [ ] **Step 2: Update imports in each moved source file**

In `src/main.py` — replace all `from config import` → `from src.config import`, all `from scraper import` → `from src.scraper import`, all `from page_utils import` → `from src.page_utils import`, all `from db import` → `from src.db import`, all `from downloader import` → `from src.downloader import`

```python
import logging
import random
import sys
import time
from src.config import (
    MOST_WANTED_URL, TOP_RATED_URL, SEARCH_BASE_URL, PROXY, WAIT_DELAY,
    COVERS_DIR, MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, REQUEST_RETRIES,
    PAGE_INTERVAL_MIN, PAGE_INTERVAL_MAX,
)
from src.scraper import parse_list_page, parse_search_page, is_javlibrary_page
from src.page_utils import load_with_cf_bypass
from src.db import (
    init_db, upsert_video, save_actresses, save_magnets,
    save_rankings, get_videos_missing_magnets, update_video_search_url,
    update_video_cover_path,
)
from src.downloader import download_cover
```

- [ ] **Step 3: Update imports in tests**

In `tests/conftest.py` — change `from db import init_db` → `from src.db import init_db`

```python
@pytest.fixture
def conn(db_path):
    from src.db import init_db
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```

In `tests/test_db.py` — change `from db import` → `from src.db import`

```python
from src.db import get_db_path, init_db
```

In `tests/test_scraper.py` — change `from scraper import` → `from src.scraper import`

```python
from src.scraper import parse_list_page, parse_search_page, is_javlibrary_page
```

In `tests/test_page_utils.py` — change `from page_utils import` → `from src.page_utils import`

```python
from src.page_utils import is_cloudflare_challenge
```

In `tests/test_downloader.py` — change `from downloader import` → `from src.downloader import`

```python
from src.downloader import download_cover
```

- [ ] **Step 4: Run existing tests to verify the move didn't break anything**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move source code into src/ directory

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Add web config and update requirements

**Files:**
- Modify: `src/config.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add web panel configuration to src/config.py**

Append to `src/config.py`:

```python
# Web panel config
WEB_HOST = os.environ.get("JAV_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("JAV_WEB_PORT", "8000"))
WEB_PASSWORD = os.environ.get("JAV_WEB_PASSWORD", "admin")
WEB_SECRET_KEY = os.environ.get("JAV_WEB_SECRET_KEY", "change-me-in-production")
```

- [ ] **Step 2: Add web dependencies to requirements.txt**

Append to `requirements.txt`:

```
fastapi
uvicorn
python-multipart
```

- [ ] **Step 3: Install new dependencies**

Run: `pip install fastapi uvicorn python-multipart`
Expected: Packages install without error

- [ ] **Step 4: Commit**

```bash
git add src/config.py requirements.txt
git commit -m "feat: add web panel config and dependencies

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Create auth module

**Files:**
- Create: `src/web/__init__.py`
- Create: `src/web/auth.py`

- [ ] **Step 1: Create web package __init__.py**

```bash
mkdir -p src/web
touch src/web/__init__.py
```

- [ ] **Step 2: Write auth.py**

Create `src/web/auth.py`:

```python
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from src.config import WEB_PASSWORD

SESSION_KEY = "authenticated"


async def require_auth(request: Request):
    if not request.session.get(SESSION_KEY):
        raise HTTPException(status_code=401)


def verify_login(request: Request, password: str) -> bool:
    if password == WEB_PASSWORD:
        request.session[SESSION_KEY] = True
        return True
    return False


def logout(request: Request):
    request.session.clear()
```

- [ ] **Step 3: Commit**

```bash
git add src/web/__init__.py src/web/auth.py
git commit -m "feat: add web auth module with session-based password protection

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Create FastAPI app with middleware and template config

**Files:**
- Create: `src/web/app.py`

- [ ] **Step 1: Write app.py**

Create `src/web/app.py`:

```python
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from src.config import WEB_SECRET_KEY
from src.web.auth import require_auth, SESSION_KEY

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="JAV Management Panel")

    app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET_KEY)

    from src.web.routes import register_routers
    register_routers(app)

    @app.exception_handler(401)
    async def auth_exception_handler(request: Request, exc):
        return RedirectResponse(url="/login", status_code=302)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

    return app


app = create_app()
```

- [ ] **Step 2: Commit**

```bash
git add src/web/app.py
git commit -m "feat: create FastAPI app with session middleware and error handlers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Create base template and error pages

**Files:**
- Create: `src/web/templates/base.html`
- Create: `src/web/templates/404.html`
- Create: `src/web/templates/500.html`

- [ ] **Step 1: Create templates directory and base.html**

```bash
mkdir -p src/web/templates
```

Create `src/web/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JAV Panel - {% block title %}{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        body { display: flex; min-height: 100vh; }
        .sidebar { width: 200px; padding: 1rem; border-right: 1px solid var(--pico-muted-border-color); }
        .sidebar nav a { display: block; padding: 0.5rem 0; text-decoration: none; }
        .sidebar nav a:hover { text-decoration: underline; }
        .sidebar nav a.active { font-weight: bold; }
        .main-content { flex: 1; padding: 1rem 2rem; }
        .topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
        .topbar form { margin: 0; display: flex; gap: 0.5rem; }
        #toast { position: fixed; bottom: 1rem; right: 1rem; z-index: 999; }
        .toast-msg { padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 0.5rem; animation: fadeOut 3s forwards; }
        .toast-success { background: var(--pico-ins-color); color: #fff; }
        .toast-error { background: var(--pico-del-color); color: #fff; }
        @keyframes fadeOut { 0%, 70% { opacity: 1; } 100% { opacity: 0; } }
        .video-table img { width: 60px; height: auto; }
        .stat-card { text-align: center; padding: 1rem; border: 1px solid var(--pico-muted-border-color); border-radius: 8px; }
        .stat-card .number { font-size: 2rem; font-weight: bold; }
        .actress-list { display: flex; flex-wrap: wrap; gap: 0.3rem; }
        .actress-tag { padding: 0.1rem 0.5rem; background: var(--pico-secondary); border-radius: 4px; font-size: 0.85rem; }
        .magnet-link { word-break: break-all; font-size: 0.85rem; font-family: monospace; }
    </style>
</head>
<body>
    <aside class="sidebar">
        <h3><a href="/" style="text-decoration:none;">JAV Panel</a></h3>
        <nav>
            <a href="/" hx-get="/" hx-target="#main" hx-push-url="true">Dashboard</a>
            <a href="/videos" hx-get="/videos" hx-target="#main" hx-push-url="true">Videos</a>
            <a href="/actresses" hx-get="/actresses" hx-target="#main" hx-push-url="true">Actresses</a>
            <a href="/magnets" hx-get="/magnets" hx-target="#main" hx-push-url="true">Magnets</a>
            <a href="/tasks" hx-get="/tasks" hx-target="#main" hx-push-url="true">Tasks</a>
        </nav>
        <hr>
        <a href="/logout" style="font-size:0.85rem;">Logout</a>
    </aside>
    <main class="main-content">
        <div class="topbar">
            <form hx-get="/videos" hx-target="#main" hx-push-url="true">
                <input type="search" name="q" placeholder="Search code or title..." style="width:300px;">
                <button type="submit">Search</button>
            </form>
        </div>
        <div id="main">
            {% block content %}{% endblock %}
        </div>
    </main>
    <div id="toast"></div>
</body>
</html>
```

- [ ] **Step 2: Create error templates**

Create `src/web/templates/404.html`:

```html
{% extends "base.html" %}
{% block title %}Not Found{% endblock %}
{% block content %}
<article>
    <h2>404 - Not Found</h2>
    <p>The page or video you're looking for doesn't exist.</p>
    <a href="/">Back to Dashboard</a>
</article>
{% endblock %}
```

Create `src/web/templates/500.html`:

```html
{% extends "base.html" %}
{% block title %}Server Error{% endblock %}
{% block content %}
<article>
    <h2>500 - Server Error</h2>
    <p>Something went wrong. Check the server logs.</p>
    <a href="/">Back to Dashboard</a>
</article>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/
git commit -m "feat: add base layout template and error pages

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Create login page

**Files:**
- Create: `src/web/routes/__init__.py`
- Create: `src/web/templates/login.html`
- Modify: `src/web/routes/__init__.py` (add login route + register_routers)

- [ ] **Step 1: Create routes package and register_routers skeleton**

```bash
mkdir -p src/web/routes
touch src/web/routes/__init__.py
```

Write `src/web/routes/__init__.py`:

```python
from fastapi import FastAPI


def register_routers(app: FastAPI):
    from src.web.routes.dashboard import router as dashboard_router
    from src.web.routes.videos import router as videos_router
    from src.web.routes.actresses import router as actresses_router
    from src.web.routes.magnets import router as magnets_router
    from src.web.routes.tasks import router as tasks_router

    app.include_router(dashboard_router)
    app.include_router(videos_router)
    app.include_router(actresses_router)
    app.include_router(magnets_router)
    app.include_router(tasks_router)

    _register_login(app)


def _register_login(app: FastAPI):
    from fastapi import Request, Form
    from fastapi.responses import RedirectResponse
    from src.web.app import templates
    from src.web.auth import verify_login, SESSION_KEY

    @app.get("/login")
    async def login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})

    @app.post("/login")
    async def login_post(request: Request, password: str = Form(...)):
        if verify_login(request, password):
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"}, status_code=401)

    @app.get("/logout")
    async def logout_route(request: Request):
        from src.web.auth import logout
        logout(request)
        return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 2: Create login template**

Create `src/web/templates/login.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JAV Panel - Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <style>
        body { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .login-card { width: 360px; padding: 2rem; }
    </style>
</head>
<body>
    <article class="login-card">
        <h2>JAV Panel</h2>
        {% if error %}
        <p style="color: var(--pico-del-color);">{{ error }}</p>
        {% endif %}
        <form method="post">
            <label>Password <input type="password" name="password" required autofocus></label>
            <button type="submit">Login</button>
        </form>
    </article>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/__init__.py src/web/templates/login.html
git commit -m "feat: add login page and auth routes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: Create dashboard route and template

**Files:**
- Create: `src/web/routes/dashboard.py`
- Create: `src/web/templates/dashboard.html`

- [ ] **Step 1: Write dashboard route**

Create `src/web/routes/dashboard.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/")
async def dashboard(request: Request):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        total_videos = conn.execute("SELECT COUNT(*) as c FROM videos").fetchone()["c"]
        total_actresses = conn.execute("SELECT COUNT(DISTINCT name) as c FROM actresses").fetchone()["c"]
        today_new = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE date(created_at) = date('now','localtime')"
        ).fetchone()["c"]
        missing_magnets = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)"
        ).fetchone()["c"]

        recent = conn.execute(
            "SELECT code, title, score, date, created_at FROM videos ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        top_most_wanted = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='most_wanted' ORDER BY r.rank LIMIT 10"""
        ).fetchall()

        top_rated = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='top_rated' ORDER BY r.rank LIMIT 10"""
        ).fetchall()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": {
                "total_videos": total_videos,
                "total_actresses": total_actresses,
                "today_new": today_new,
                "missing_magnets": missing_magnets,
            },
            "recent": recent,
            "top_most_wanted": top_most_wanted,
            "top_rated": top_rated,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Write dashboard template**

Create `src/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<h2>Dashboard</h2>

<div class="grid">
    <div class="stat-card">
        <div class="number">{{ stats.total_videos }}</div>
        <div>Total Videos</div>
    </div>
    <div class="stat-card">
        <div class="number">{{ stats.total_actresses }}</div>
        <div>Actresses</div>
    </div>
    <div class="stat-card">
        <div class="number">{{ stats.today_new }}</div>
        <div>Today New</div>
    </div>
    <div class="stat-card">
        <div class="number">{{ stats.missing_magnets }}</div>
        <div>Missing Magnets</div>
    </div>
</div>

<div class="grid">
    <div>
        <h3>Most Wanted Top 10</h3>
        <table>
            <thead><tr><th>#</th><th>Code</th><th>Title</th><th>Score</th></tr></thead>
            <tbody>
            {% for v in top_most_wanted %}
            <tr>
                <td>{{ v.rank }}</td>
                <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
                <td>{{ v.title[:50] if v.title else '' }}</td>
                <td>{{ v.score }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div>
        <h3>Top Rated Top 10</h3>
        <table>
            <thead><tr><th>#</th><th>Code</th><th>Title</th><th>Score</th></tr></thead>
            <tbody>
            {% for v in top_rated %}
            <tr>
                <td>{{ v.rank }}</td>
                <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
                <td>{{ v.title[:50] if v.title else '' }}</td>
                <td>{{ v.score }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<h3>Recently Added</h3>
<table>
    <thead><tr><th>Code</th><th>Title</th><th>Score</th><th>Date</th></tr></thead>
    <tbody>
    {% for v in recent %}
    <tr>
        <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
        <td>{{ v.title[:60] if v.title else '' }}</td>
        <td>{{ v.score }}</td>
        <td>{{ v.date }}</td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/dashboard.py src/web/templates/dashboard.html
git commit -m "feat: add dashboard with stats cards and ranking tables

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: Create videos list route and template

**Files:**
- Create: `src/web/routes/videos.py`
- Create: `src/web/templates/videos.html`

- [ ] **Step 1: Write videos route**

Create `src/web/routes/videos.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/videos", dependencies=[Depends(require_auth)])

PAGE_SIZE = 20


@router.get("")
async def video_list(
    request: Request,
    q: str = Query(default=""),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    list_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    valid_sorts = {"code", "title", "score", "date", "created_at"}
    if sort not in valid_sorts:
        sort = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        where_clauses = []
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        if list_type:
            where_clauses.append("r.list_type = ?")
            params.append(list_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(DISTINCT v.code) as c FROM videos v
            LEFT JOIN rankings r ON v.code = r.video_code
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT DISTINCT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at, r.list_type, r.rank
            FROM videos v
            LEFT JOIN rankings r ON v.code = r.video_code
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template = "videos.html"
        if request.headers.get("HX-Request"):
            template = "videos_partial.html"

        return templates.TemplateResponse(template, {
            "request": request,
            "videos": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "q": q,
            "sort": sort,
            "order": order,
            "list_type": list_type,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Write videos list template**

Create `src/web/templates/videos.html`:

```html
{% extends "base.html" %}
{% block title %}Videos{% endblock %}
{% block content %}
<h2>Videos ({{ total }})</h2>

<div style="display:flex; gap:1rem; margin-bottom:1rem;">
    <form hx-get="/videos" hx-target="#main" hx-push-url="true" style="display:flex; gap:0.5rem; align-items:end;">
        <input type="hidden" name="q" value="{{ q }}">
        <input type="hidden" name="sort" value="{{ sort }}">
        <input type="hidden" name="order" value="{{ order }}">
        <label>Filter by list
            <select name="list_type" onchange="this.form.dispatchEvent(new Event('submit',{bubbles:true}))">
                <option value="">All</option>
                <option value="most_wanted" {% if list_type=='most_wanted' %}selected{% endif %}>Most Wanted</option>
                <option value="top_rated" {% if list_type=='top_rated' %}selected{% endif %}>Top Rated</option>
            </select>
        </label>
        <noscript><button type="submit">Filter</button></noscript>
    </form>
</div>

{% include "videos_partial.html" %}
{% endblock %}
```

Create `src/web/templates/videos_partial.html`:

```html
<div id="video-table">
<table class="video-table">
    <thead>
        <tr>
            <th>Cover</th>
            <th><a hx-get="/videos?q={{ q }}&sort=code&order={% if sort=='code' and order=='asc' %}desc{% else %}asc{% endif %}&list_type={{ list_type }}" hx-target="#main" hx-push-url="true">Code</a></th>
            <th>Title</th>
            <th><a hx-get="/videos?q={{ q }}&sort=score&order={% if sort=='score' and order=='desc' %}asc{% else %}desc{% endif %}&list_type={{ list_type }}" hx-target="#main" hx-push-url="true">Score</a></th>
            <th><a hx-get="/videos?q={{ q }}&sort=date&order={% if sort=='date' and order=='desc' %}asc{% else %}desc{% endif %}&list_type={{ list_type }}" hx-target="#main" hx-push-url="true">Date</a></th>
            <th>Maker</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
    {% for v in videos %}
    <tr>
        <td>{% if v.cover_url %}<img src="{{ v.cover_url }}" alt="cover" loading="lazy">{% endif %}</td>
        <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
        <td>{{ v.title[:60] if v.title else '' }}</td>
        <td>{{ v.score }}</td>
        <td>{{ v.date }}</td>
        <td>{{ v.maker or '' }}</td>
        <td>
            <a href="/videos/{{ v.code }}">Detail</a>
            <a href="/videos/{{ v.code }}/edit" hx-get="/videos/{{ v.code }}/edit" hx-target="closest tr" hx-swap="outerHTML">Edit</a>
        </td>
    </tr>
    {% endfor %}
    </tbody>
</table>

{% if total_pages > 1 %}
<nav>
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

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/videos.py src/web/templates/videos.html src/web/templates/videos_partial.html
git commit -m "feat: add video list with search, sort, filter, and pagination

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: Create video detail page

**Files:**
- Create: `src/web/templates/video_detail.html`
- Modify: `src/web/routes/videos.py`

- [ ] **Step 1: Add detail route to videos.py**

Append to `src/web/routes/videos.py`:

```python
@router.get("/{code}")
async def video_detail(request: Request, code: str):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
        if not video:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

        actresses = conn.execute(
            "SELECT name FROM actresses WHERE video_code=? ORDER BY name", (code,)
        ).fetchall()

        magnets = conn.execute(
            "SELECT magnet, source, created_at FROM magnets WHERE video_code=? ORDER BY created_at DESC", (code,)
        ).fetchall()

        rankings = conn.execute(
            "SELECT list_type, rank FROM rankings WHERE video_code=?", (code,)
        ).fetchall()

        return templates.TemplateResponse("video_detail.html", {
            "request": request,
            "video": video,
            "actresses": actresses,
            "magnets": magnets,
            "rankings": rankings,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Write detail template**

Create `src/web/templates/video_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ video.code }}{% endblock %}
{% block content %}
<article>
    <div class="grid">
        <div>
            {% if video.cover_url %}
            <img src="{{ video.cover_url }}" alt="cover" style="max-width:100%;">
            {% endif %}
        </div>
        <div>
            <h2>{{ video.code }}</h2>
            <p><strong>{{ video.title }}</strong></p>
            <table>
                <tr><td>Score</td><td>{{ video.score }}</td></tr>
                <tr><td>Date</td><td>{{ video.date }}</td></tr>
                <tr><td>Duration</td><td>{{ video.duration or '-' }}</td></tr>
                <tr><td>Maker</td><td>{{ video.maker or '-' }}</td></tr>
                <tr><td>Label</td><td>{{ video.label or '-' }}</td></tr>
                {% if video.search_url %}
                <tr><td>Search</td><td><a href="{{ video.search_url }}" target="_blank">clg55</a></td></tr>
                {% endif %}
            </table>

            {% if rankings %}
            <p>
                {% for r in rankings %}
                <span class="actress-tag">{{ r.list_type }} #{{ r.rank }}</span>
                {% endfor %}
            </p>
            {% endif %}

            <a href="/videos/{{ video.code }}/edit" role="button"
               hx-get="/videos/{{ video.code }}/edit" hx-target="closest article" hx-swap="outerHTML">Edit</a>
        </div>
    </div>

    <h3>Actresses</h3>
    <div class="actress-list">
    {% for a in actresses %}
        <span class="actress-tag">
            <a href="/actresses?q={{ a.name }}" style="color:inherit;">{{ a.name }}</a>
        </span>
    {% endfor %}
    </div>
    {% if not actresses %}<p>No actresses listed.</p>{% endif %}

    <h3>Magnets ({{ magnets|length }})</h3>
    {% if magnets %}
    <ul>
    {% for m in magnets %}
        <li class="magnet-link">
            <a href="{{ m.magnet }}">{{ m.magnet[:80] }}...</a>
            <small>({{ m.source }}, {{ m.created_at }})</small>
        </li>
    {% endfor %}
    </ul>
    {% else %}
    <p>No magnets found.</p>
    {% endif %}
</article>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/videos.py src/web/templates/video_detail.html
git commit -m "feat: add video detail page with actresses, magnets, and rankings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: Create video edit functionality

**Files:**
- Create: `src/web/templates/video_edit.html`
- Modify: `src/web/routes/videos.py`

- [ ] **Step 1: Add edit routes to videos.py**

Append to `src/web/routes/videos.py`:

```python
@router.get("/{code}/edit")
async def video_edit_form(request: Request, code: str):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
        if not video:
            return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
        return templates.TemplateResponse("video_edit.html", {"request": request, "video": video, "error": None})
    finally:
        conn.close()


@router.post("/{code}/edit")
async def video_edit_save(request: Request, code: str):
    from fastapi import Form
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        body = await request.form()
        title = body.get("title", "").strip()
        if not title:
            video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
            return templates.TemplateResponse("video_edit.html", {"request": request, "video": video, "error": "Title is required"}, status_code=422)

        conn.execute("""
            UPDATE videos SET title=?, score=?, date=?, duration=?, maker=?, label=?, updated_at=datetime('now','localtime')
            WHERE code=?
        """, (
            title,
            float(body.get("score", 0) or 0),
            body.get("date", ""),
            body.get("duration", ""),
            body.get("maker", ""),
            body.get("label", ""),
            code,
        ))
        conn.commit()

        if request.headers.get("HX-Request"):
            video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
            actresses = conn.execute("SELECT name FROM actresses WHERE video_code=? ORDER BY name", (code,)).fetchall()
            magnets = conn.execute("SELECT magnet, source, created_at FROM magnets WHERE video_code=?", (code,)).fetchall()
            rankings = conn.execute("SELECT list_type, rank FROM rankings WHERE video_code=?", (code,)).fetchall()
            resp = templates.TemplateResponse("video_detail.html", {
                "request": request, "video": video,
                "actresses": actresses, "magnets": magnets, "rankings": rankings,
            })
            resp.headers["HX-Trigger"] = '{"toast": {"msg": "Saved successfully", "type": "success"}}'
            return resp

        return RedirectResponse(url=f"/videos/{code}", status_code=302)
    finally:
        conn.close()
```

- [ ] **Step 2: Write edit form template**

Create `src/web/templates/video_edit.html`:

```html
<article>
    <h2>Edit {{ video.code }}</h2>
    {% if error %}<p style="color:var(--pico-del-color);">{{ error }}</p>{% endif %}
    <form hx-post="/videos/{{ video.code }}/edit" hx-target="closest article" hx-swap="outerHTML">
        <label>Code <input type="text" value="{{ video.code }}" disabled></label>
        <label>Title <input type="text" name="title" value="{{ video.title or '' }}" required></label>
        <div class="grid">
            <label>Score <input type="number" name="score" step="0.1" min="0" max="10" value="{{ video.score or 0 }}"></label>
            <label>Date <input type="text" name="date" value="{{ video.date or '' }}"></label>
            <label>Duration <input type="text" name="duration" value="{{ video.duration or '' }}"></label>
            <label>Maker <input type="text" name="maker" value="{{ video.maker or '' }}"></label>
            <label>Label <input type="text" name="label" value="{{ video.label or '' }}"></label>
        </div>
        <button type="submit">Save</button>
        <a href="/videos/{{ video.code }}" hx-get="/videos/{{ video.code }}" hx-target="closest article" hx-swap="outerHTML" role="button" class="secondary">Cancel</a>
    </form>
</article>
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/videos.py src/web/templates/video_edit.html
git commit -m "feat: add inline video edit with HTMX form submission

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: Create actresses route and template

**Files:**
- Create: `src/web/routes/actresses.py`
- Create: `src/web/templates/actresses.html`

- [ ] **Step 1: Write actresses route**

Create `src/web/routes/actresses.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/actresses", dependencies=[Depends(require_auth)])


@router.get("")
async def actress_list(request: Request, q: str = Query(default="")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if q:
            rows = conn.execute("""
                SELECT a.name, COUNT(*) as video_count
                FROM actresses a
                WHERE a.name LIKE ?
                GROUP BY a.name ORDER BY video_count DESC
            """, (f"%{q}%",)).fetchall()
        else:
            rows = conn.execute("""
                SELECT name, COUNT(*) as video_count
                FROM actresses GROUP BY name ORDER BY video_count DESC
                LIMIT 200
            """).fetchall()

        return templates.TemplateResponse("actresses.html", {
            "request": request, "actresses": rows, "q": q,
        })
    finally:
        conn.close()


@router.get("/{name}/videos")
async def actress_videos(request: Request, name: str):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        videos = conn.execute("""
            SELECT v.code, v.title, v.score, v.date, v.cover_url
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? ORDER BY v.date DESC
        """, (name,)).fetchall()

        return templates.TemplateResponse("actress_videos_partial.html", {
            "request": request, "name": name, "videos": videos,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Write actresses template**

Create `src/web/templates/actresses.html`:

```html
{% extends "base.html" %}
{% block title %}Actresses{% endblock %}
{% block content %}
<h2>Actresses</h2>

<form hx-get="/actresses" hx-target="#main" hx-push-url="true">
    <input type="search" name="q" value="{{ q }}" placeholder="Search actress name...">
    <button type="submit">Search</button>
</form>

<table>
    <thead><tr><th>Name</th><th>Videos</th><th></th></tr></thead>
    <tbody>
    {% for a in actresses %}
    <tr>
        <td>{{ a.name }}</td>
        <td>{{ a.video_count }}</td>
        <td>
            <button hx-get="/actresses/{{ a.name }}/videos"
                    hx-target="next tr" hx-swap="afterend"
                    hx-trigger="click once">Show videos</button>
        </td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}
```

Create `src/web/templates/actress_videos_partial.html`:

```html
<tr><td colspan="3" style="padding:0;">
    <table>
    <thead><tr><th>Cover</th><th>Code</th><th>Title</th><th>Score</th><th>Date</th></tr></thead>
    <tbody>
    {% for v in videos %}
    <tr>
        <td>{% if v.cover_url %}<img src="{{ v.cover_url }}" style="width:40px;">{% endif %}</td>
        <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
        <td>{{ v.title[:50] if v.title else '' }}</td>
        <td>{{ v.score }}</td>
        <td>{{ v.date }}</td>
    </tr>
    {% endfor %}
    </tbody>
    </table>
</td></tr>
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/actresses.py src/web/templates/actresses.html src/web/templates/actress_videos_partial.html
git commit -m "feat: add actress aggregation page with lazy-loaded video lists

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: Create magnets management route and template

**Files:**
- Create: `src/web/routes/magnets.py`
- Create: `src/web/templates/magnets.html`

- [ ] **Step 1: Write magnets route**

Create `src/web/routes/magnets.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/magnets", dependencies=[Depends(require_auth)])


@router.get("")
async def magnet_list(request: Request):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        missing = conn.execute("""
            SELECT code, title, date, created_at FROM videos
            WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)
            ORDER BY created_at DESC LIMIT 50
        """).fetchall()

        has_magnets = conn.execute("""
            SELECT v.code, v.title, COUNT(m.id) as magnet_count
            FROM videos v JOIN magnets m ON v.code = m.video_code
            GROUP BY v.code ORDER BY magnet_count DESC LIMIT 50
        """).fetchall()

        return templates.TemplateResponse("magnets.html", {
            "request": request, "missing": missing, "has_magnets": has_magnets,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Write magnets template**

Create `src/web/templates/magnets.html`:

```html
{% extends "base.html" %}
{% block title %}Magnets{% endblock %}
{% block content %}
<h2>Magnets</h2>

<h3>Missing Magnets ({{ missing|length }})</h3>
{% if missing %}
<table>
    <thead><tr><th>Code</th><th>Title</th><th>Date</th><th>Added</th></tr></thead>
    <tbody>
    {% for v in missing %}
    <tr>
        <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
        <td>{{ v.title[:60] if v.title else '' }}</td>
        <td>{{ v.date }}</td>
        <td>{{ v.created_at[:10] }}</td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% else %}
<p>All videos have magnets.</p>
{% endif %}

<h3>Videos With Magnets</h3>
{% if has_magnets %}
<table>
    <thead><tr><th>Code</th><th>Title</th><th>Magnets</th></tr></thead>
    <tbody>
    {% for v in has_magnets %}
    <tr>
        <td><a href="/videos/{{ v.code }}">{{ v.code }}</a></td>
        <td>{{ v.title[:60] if v.title else '' }}</td>
        <td>{{ v.magnet_count }}</td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% else %}
<p>No magnets found.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/magnets.py src/web/templates/magnets.html
git commit -m "feat: add magnet management page showing missing and completed videos

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 13: Create tasks page (manual scrape trigger)

**Files:**
- Create: `src/web/routes/tasks.py`
- Create: `src/web/templates/tasks.html`

- [ ] **Step 1: Write tasks route with background job support**

Create `src/web/routes/tasks.py`:

```python
import sqlite3
import threading
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/tasks", dependencies=[Depends(require_auth)])

_task_status: dict[str, dict] = {}


def _run_scrape(task_id: str, list_type: str):
    _task_status[task_id] = {"status": "running", "message": f"Scraping {list_type}...", "started_at": datetime.now().isoformat()}
    try:
        from src.main import main as scrape_main
        scrape_main()
        _task_status[task_id] = {"status": "done", "message": "Scrape completed successfully", "finished_at": datetime.now().isoformat()}
    except Exception as e:
        _task_status[task_id] = {"status": "error", "message": str(e), "finished_at": datetime.now().isoformat()}


def _run_backfill(task_id: str):
    _task_status[task_id] = {"status": "running", "message": "Backfilling magnets...", "started_at": datetime.now().isoformat()}
    try:
        from src.config import MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, SEARCH_BASE_URL, PROXY
        from src.db import init_db, get_videos_missing_magnets, update_video_search_url, save_magnets
        from src.scraper import parse_search_page
        from src.page_utils import load_with_cf_bypass
        import random, time

        conn = init_db()
        try:
            codes = get_videos_missing_magnets(conn, days=MAGNET_BACKFILL_DAYS, limit=MAX_BACKFILL_COUNT)
            for code in codes:
                _task_status[task_id]["message"] = f"Searching {code}..."
                search_url = f"{SEARCH_BASE_URL}/search/{code}"
                html = load_with_cf_bypass(search_url, proxy=PROXY, wait=random.uniform(3, 5), timeout=30, headless=True)
                if html:
                    _, magnets = parse_search_page(html, search_url)
                    if search_url:
                        update_video_search_url(conn, code, search_url)
                    if magnets:
                        save_magnets(conn, code, magnets)
                time.sleep(random.uniform(3, 5))
            _task_status[task_id] = {"status": "done", "message": f"Backfill complete: {len(codes)} videos processed", "finished_at": datetime.now().isoformat()}
        finally:
            conn.close()
    except Exception as e:
        _task_status[task_id] = {"status": "error", "message": str(e), "finished_at": datetime.now().isoformat()}


@router.get("")
async def tasks_page(request: Request):
    return templates.TemplateResponse("tasks.html", {
        "request": request, "tasks": _task_status,
    })


@router.post("/scrape")
async def trigger_scrape(request: Request, list_type: str = "all"):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_scrape, args=(task_id, list_type), daemon=True)
    t.start()
    resp = templates.TemplateResponse("tasks.html", {"request": request, "tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Scrape task started", "type": "success"}}'
    return resp


@router.post("/backfill")
async def trigger_backfill(request: Request):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_backfill, args=(task_id,), daemon=True)
    t.start()
    resp = templates.TemplateResponse("tasks.html", {"request": request, "tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Backfill task started", "type": "success"}}'
    return resp


@router.get("/status")
async def task_status(request: Request):
    return templates.TemplateResponse("task_status_partial.html", {
        "request": request, "tasks": _task_status,
    })
```

- [ ] **Step 2: Write tasks template**

Create `src/web/templates/tasks.html`:

```html
{% extends "base.html" %}
{% block title %}Tasks{% endblock %}
{% block content %}
<h2>Tasks</h2>

<div class="grid">
    <article>
        <h3>Trigger Scrape</h3>
        <p>Run the full scrape pipeline (list pages + magnets for new videos + backfill).</p>
        <button hx-post="/tasks/scrape" hx-target="#task-list" hx-swap="innerHTML">
            Start Scrape
        </button>
    </article>
    <article>
        <h3>Trigger Backfill</h3>
        <p>Search magnets for videos that are missing them (within configured date range).</p>
        <button hx-post="/tasks/backfill" hx-target="#task-list" hx-swap="innerHTML">
            Start Backfill
        </button>
    </article>
</div>

<div id="task-list" hx-get="/tasks/status" hx-trigger="every 3s" hx-swap="innerHTML">
    {% include "task_status_partial.html" %}
</div>
{% endblock %}
```

Create `src/web/templates/task_status_partial.html`:

```html
<h3>Task History</h3>
{% if tasks %}
<table>
    <thead><tr><th>ID</th><th>Status</th><th>Message</th><th>Started</th><th>Finished</th></tr></thead>
    <tbody>
    {% for tid, task in tasks.items() %}
    <tr>
        <td>{{ tid }}</td>
        <td>
            {% if task.status == 'running' %}🔄 Running
            {% elif task.status == 'done' %}✅ Done
            {% else %}❌ Error
            {% endif %}
        </td>
        <td>{{ task.message }}</td>
        <td>{{ task.get('started_at', '-')[:19] }}</td>
        <td>{{ task.get('finished_at', '-')[:19] if task.get('finished_at') else '-' }}</td>
    </tr>
    {% endfor %}
    </tbody>
</table>
{% else %}
<p>No tasks run yet.</p>
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/tasks.py src/web/templates/tasks.html src/web/templates/task_status_partial.html
git commit -m "feat: add manual scrape/backfill trigger with background tasks and polling

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 14: Create run script

**Files:**
- Create: `run_web.py` (project root)

- [ ] **Step 1: Write run script**

Create `run_web.py`:

```python
import uvicorn
from src.config import WEB_HOST, WEB_PORT

if __name__ == "__main__":
    uvicorn.run("src.web.app:app", host=WEB_HOST, port=WEB_PORT, reload=True)
```

- [ ] **Step 2: Commit**

```bash
git add run_web.py
git commit -m "feat: add web server launch script

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 15: Write web integration tests

**Files:**
- Create: `tests/test_web.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add web test fixtures to conftest.py**

Append to `tests/conftest.py`:

```python
import sqlite3 as _sqlite3


@pytest.fixture
def web_db_path(tmp_path, monkeypatch):
    """Override get_db_path to point to a temp DB pre-populated with sample data."""
    db_path = str(tmp_path / "jav.db")
    import src.db
    conn = src.db.init_db(db_path)
    conn.row_factory = _sqlite3.Row

    videos = [
        ("TEST-001", "Test Video One", "http://example.com/1.jpg", 4.5, "2026-01-01", "120", "Maker A", "Label X"),
        ("TEST-002", "Test Video Two", "http://example.com/2.jpg", 3.8, "2026-02-01", "90", "Maker B", "Label Y"),
        ("TEST-003", "Another Video", "", 4.0, "2026-03-01", "150", "Maker A", ""),
    ]
    for v in videos:
        conn.execute(
            "INSERT INTO videos (code, title, cover_url, score, date, duration, maker, label) VALUES (?,?,?,?,?,?,?,?)",
            v,
        )
    conn.execute("INSERT INTO actresses (video_code, name) VALUES ('TEST-001', 'Alice')")
    conn.execute("INSERT INTO actresses (video_code, name) VALUES ('TEST-001', 'Bob')")
    conn.execute("INSERT INTO actresses (video_code, name) VALUES ('TEST-002', 'Alice')")
    conn.execute("INSERT INTO rankings (video_code, list_type, rank) VALUES ('TEST-001', 'most_wanted', 1)")
    conn.execute("INSERT INTO rankings (video_code, list_type, rank) VALUES ('TEST-002', 'top_rated', 3)")
    conn.execute("INSERT INTO magnets (video_code, magnet, source) VALUES ('TEST-001', 'magnet:?xt=urn:btih:AAA', 'clg55')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(src.db, "get_db_path", lambda: db_path)
    return db_path


@pytest.fixture
def web_client(web_db_path):
    from fastapi.testclient import TestClient
    from src.web.app import app
    client = TestClient(app)
    client.post("/login", data={"password": "admin"})
    return client
```

- [ ] **Step 2: Write test file**

Create `tests/test_web.py`:

```python
import pytest
from fastapi.testclient import TestClient


class TestAuth:
    def test_login_page_returns_200(self):
        from src.web.app import app
        client = TestClient(app)
        response = client.get("/login")
        assert response.status_code == 200
        assert b"Login" in response.content

    def test_login_with_wrong_password(self):
        from src.web.app import app
        client = TestClient(app)
        response = client.post("/login", data={"password": "wrong"})
        assert response.status_code == 401
        assert b"Invalid password" in response.content

    def test_login_with_correct_password(self):
        from src.web.app import app
        client = TestClient(app)
        response = client.post("/login", data={"password": "admin"})
        assert response.status_code == 302
        assert response.headers["location"] == "/"

    def test_protected_route_redirects_to_login(self):
        from src.web.app import app
        client = TestClient(app)
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"

    def test_logout_clears_session(self):
        from src.web.app import app
        client = TestClient(app)
        client.post("/login", data={"password": "admin"})
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        # After logout, accessing protected route should redirect to login
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "/login"


class TestDashboard:
    def test_dashboard_returns_200(self, web_client):
        response = web_client.get("/")
        assert response.status_code == 200
        assert b"Dashboard" in response.content
        assert b"3" in response.content  # total videos

    def test_dashboard_has_stats(self, web_client):
        response = web_client.get("/")
        assert b"Total Videos" in response.content
        assert b"Actresses" in response.content
        assert b"Missing Magnets" in response.content


class TestVideos:
    def test_video_list_returns_200(self, web_client):
        response = web_client.get("/videos")
        assert response.status_code == 200
        assert b"TEST-001" in response.content
        assert b"TEST-002" in response.content

    def test_video_list_search(self, web_client):
        response = web_client.get("/videos?q=Another")
        assert response.status_code == 200
        assert b"TEST-003" in response.content
        assert b"TEST-001" not in response.content

    def test_video_list_filter_by_list_type(self, web_client):
        response = web_client.get("/videos?list_type=most_wanted")
        assert response.status_code == 200
        assert b"TEST-001" in response.content

    def test_video_detail_returns_200(self, web_client):
        response = web_client.get("/videos/TEST-001")
        assert response.status_code == 200
        assert b"Test Video One" in response.content
        assert b"Alice" in response.content
        assert b"Bob" in response.content

    def test_video_detail_has_magnets(self, web_client):
        response = web_client.get("/videos/TEST-001")
        assert b"magnet:" in response.content

    def test_video_detail_has_rankings(self, web_client):
        response = web_client.get("/videos/TEST-001")
        assert b"most_wanted" in response.content

    def test_video_detail_404(self, web_client):
        response = web_client.get("/videos/NONEXISTENT")
        assert response.status_code == 404

    def test_video_edit_form_returns_200(self, web_client):
        response = web_client.get("/videos/TEST-001/edit")
        assert response.status_code == 200
        assert b"Edit" in response.content

    def test_video_edit_save(self, web_client):
        response = web_client.post("/videos/TEST-001/edit", data={
            "title": "Updated Title", "score": "5.0", "date": "2026-05-01",
            "duration": "180", "maker": "New Maker", "label": "New Label",
        })
        assert response.status_code == 200
        assert b"Updated Title" in response.content


class TestActresses:
    def test_actress_list_returns_200(self, web_client):
        response = web_client.get("/actresses")
        assert response.status_code == 200
        assert b"Alice" in response.content
        assert b"Bob" in response.content

    def test_actress_list_has_counts(self, web_client):
        response = web_client.get("/actresses")
        assert b"2" in response.content  # Alice has 2 videos

    def test_actress_videos_endpoint(self, web_client):
        response = web_client.get("/actresses/Alice/videos")
        assert response.status_code == 200
        assert b"TEST-001" in response.content
        assert b"TEST-002" in response.content


class TestMagnets:
    def test_magnet_list_returns_200(self, web_client):
        response = web_client.get("/magnets")
        assert response.status_code == 200
        assert b"TEST-002" in response.content  # missing magnets


class TestTasks:
    def test_tasks_page_returns_200(self, web_client):
        response = web_client.get("/tasks")
        assert response.status_code == 200
        assert b"Trigger Scrape" in response.content
        assert b"Trigger Backfill" in response.content

    def test_trigger_scrape_returns_200(self, web_client):
        response = web_client.post("/tasks/scrape")
        assert response.status_code == 200

    def test_trigger_backfill_returns_200(self, web_client):
        response = web_client.post("/tasks/backfill")
        assert response.status_code == 200

    def test_task_status_returns_200(self, web_client):
        response = web_client.get("/tasks/status")
        assert response.status_code == 200
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_web.py -v`
Expected: All tests PASS

- [ ] **Step 4: Run all tests to ensure no regressions**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_web.py
git commit -m "test: add web panel integration tests for all routes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 16: Final verification

- [ ] **Step 1: Verify app starts without errors**

Run: `python -c "from src.web.app import app; print('App loaded successfully')"`
Expected: `App loaded successfully`

- [ ] **Step 2: Verify all tests pass**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
git add -A
git commit -m "chore: final verification and cleanup

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
