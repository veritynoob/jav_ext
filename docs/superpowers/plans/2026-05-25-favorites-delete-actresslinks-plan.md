# Favorites, Delete & Actress Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add video favorites (toggle on cards + detail), soft delete, favorites list page, and javlibrary actress links on detail page.

**Architecture:** New `favorites` table + `deleted`/`deleted_at` columns on videos + `actress_id` on actresses. Two new endpoints (POST favorite toggle, POST delete). New `/favorites` page reusing the videos grid pattern. Scraper updated to extract actress IDs from detail page hrefs.

**Tech Stack:** FastAPI, Jinja2, HTMX 2.0, Pico CSS, SQLite

---

### Task 1: Database — add tables, columns, and helper functions

**Files:**
- Modify: `src/db.py`

- [ ] **Step 1: Add favorites table to init_db()**

In `src/db.py`, inside `init_db()`'s `conn.executescript()`, add after the magnets table:

```sql
CREATE TABLE IF NOT EXISTS favorites (
    video_code TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (video_code) REFERENCES videos(code) ON DELETE CASCADE
);
```

- [ ] **Step 2: Add migration blocks for new columns**

After the existing migration blocks in `init_db()`, add:

```python
# Migration: soft-delete columns on videos
for col in [("deleted", "INTEGER NOT NULL DEFAULT 0"), ("deleted_at", "TEXT")]:
    try:
        conn.execute(f"ALTER TABLE videos ADD COLUMN {col[0]} {col[1]}")
    except sqlite3.OperationalError:
        pass

# Migration: actress_id on actresses
try:
    conn.execute("ALTER TABLE actresses ADD COLUMN actress_id TEXT")
except sqlite3.OperationalError:
    pass
```

- [ ] **Step 3: Update save_actresses() to accept (name, actress_id) tuples**

Replace the existing `save_actresses()` function with:

```python
def save_actresses(conn, video_code, actresses):
    """Save actresses for a video. Accepts both name strings and (name, actress_id) tuples."""
    conn.execute("DELETE FROM actresses WHERE video_code=?", (video_code,))
    for item in actresses:
        if isinstance(item, str):
            name = item.strip()
            actress_id = None
        else:
            name = item[0].strip()
            actress_id = item[1] if len(item) > 1 and item[1] else None
        if name:
            conn.execute(
                "INSERT INTO actresses (video_code, name, actress_id) VALUES (?, ?, ?)",
                (video_code, name, actress_id)
            )
    conn.commit()
```

- [ ] **Step 4: Add favorite toggle function**

After `save_actresses()`, add:

```python
def toggle_favorite(conn, video_code):
    """Toggle favorite status. Returns new state (True=favorited, False=unfavorited)."""
    row = conn.execute(
        "SELECT video_code FROM favorites WHERE video_code=?", (video_code,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM favorites WHERE video_code=?", (video_code,))
        conn.commit()
        return False
    else:
        conn.execute(
            "INSERT INTO favorites (video_code) VALUES (?)", (video_code,)
        )
        conn.commit()
        return True
```

- [ ] **Step 5: Add soft_delete_video() function**

```python
def soft_delete_video(conn, video_code):
    """Soft-delete a video by setting deleted=1."""
    conn.execute(
        "UPDATE videos SET deleted=1, deleted_at=datetime('now','localtime'), updated_at=datetime('now','localtime') WHERE code=?",
        (video_code,)
    )
    conn.commit()
```

- [ ] **Step 6: Run existing tests to verify no regressions**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_db.py -v
```

Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/db.py
git commit -m "feat: add favorites table, soft-delete columns, actress_id, and helpers

- Add favorites table to init_db schema
- Add deleted/deleted_at columns on videos (migration)
- Add actress_id column on actresses (migration)
- Update save_actresses to accept (name, actress_id) tuples
- Add toggle_favorite() and soft_delete_video() helpers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Scraper — extract actress ID from detail pages

**Files:**
- Modify: `src/scraper.py`

- [ ] **Step 1: Update parse_detail_page() to extract actress IDs**

In `src/scraper.py`, replace the actress extraction block in `parse_detail_page()` (lines 184-188):

```python
    actresses = []
    for a_el in soup.select("#video_cast .cast .star a[href*=vl_star]"):
        name = a_el.text.strip()
        if not name:
            continue
        href = a_el.get("href", "")
        m = re.search(r's=(\w+)', href)
        actress_id = m.group(1) if m else ""
        actresses.append((name, actress_id))
```

The return dict's `"actresses"` key now contains a list of `(name, actress_id)` tuples.

- [ ] **Step 2: Update existing tests for the new actress format**

In `tests/test_scraper.py`, the tests at lines 94-107 expect `result["actresses"] == ["Actress One", "Actress Two"]` (plain strings). The test fixture `video_detail.html` doesn't exist yet so this test currently fails regardless. Add the fixture and update the assertion:

First, create `tests/fixtures/video_detail.html`:

```html
<!DOCTYPE html>
<html>
<body>
<div id="video_date"><table><tr><td class="text">2024-06-15</td></tr></table></div>
<div id="video_length"><table><tr><td><span class="text">120</span></td></tr></table></div>
<div id="video_maker"><table><tr><td class="text"><a href="/m.php?id=1">Studio X</a></td></tr></table></div>
<div id="video_label"><table><tr><td class="text"><a href="/l.php?id=2">Label Y</a></td></tr></table></div>
<div id="video_cast" class="item">
    <table><tr>
    <td class="text">
        <span class="cast"><span class="star"><a href="vl_star.php?s=aaa111" rel="tag">Actress One</a></span></span>
        <span class="cast"><span class="star"><a href="vl_star.php?s=bbb222" rel="tag">Actress Two</a></span></span>
    </td>
    </tr></table>
</div>
<div class="score">(8.52)</div>
<img id="video_jacket_img" src="//pics.javlibrary.com/abc-123.jpg">
</body>
</html>
```

Then update the test at line 105:

```python
# Change from:
assert result["actresses"] == ["Actress One", "Actress Two"]
# To:
assert result["actresses"] == [("Actress One", "aaa111"), ("Actress Two", "bbb222")]
```

- [ ] **Step 3: Update edge case test for empty actresses**

In `tests/test_scraper.py`, line 335:
```python
assert result["actresses"] == []
```
This already works since an empty list is still an empty list.

Also add a test for actress without vl_star href:

```python
def test_actress_without_id(self):
    html = """
    <div id="video_cast">
        <span class="cast"><span class="star"><a href="vl_star.php?s=xyz789" rel="tag">With ID</a></span></span>
    </div>
    """
    result = parse_detail_page(html)
    assert result["actresses"] == [("With ID", "xyz789")]
```

- [ ] **Step 4: Run scraper tests**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_scraper.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/scraper.py tests/fixtures/video_detail.html tests/test_scraper.py
git commit -m "feat: extract actress ID from javlibrary detail page hrefs

parse_detail_page now returns (name, actress_id) tuples for actresses.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Routes — favorite toggle, delete, and deleted=0 filter

**Files:**
- Modify: `src/web/routes/videos.py`

- [ ] **Step 1: Update video_list query to filter deleted=0**

In `videos.py`, change the `count_sql` line (46):

```python
count_sql = f"SELECT COUNT(*) as c FROM videos v WHERE v.deleted=0 {'AND ' + ' AND '.join(where_clauses) if where_clauses else ''}"
```

Wait — cleaner approach. Add `WHERE v.deleted=0` to the base clauses:

Replace the where_clauses block (lines 32-44):

```python
        where_clauses = ["v.deleted=0"]
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        if list_type:
            where_clauses.append("v.code IN (SELECT video_code FROM rankings WHERE list_type = ?)")
            params.append(list_type)

        where_sql = "WHERE " + " AND ".join(where_clauses)
```

- [ ] **Step 2: Update video_detail query to filter deleted=0 and include favorite state**

In the `video_detail()` function, change the video query (line 84):

```python
        video = conn.execute(
            "SELECT v.*, f.video_code as is_favorited FROM videos v "
            "LEFT JOIN favorites f ON v.code = f.video_code "
            "WHERE v.code=? AND v.deleted=0", (code,)
        ).fetchone()
```

Pass `is_favorited` to the template: add `"is_favorited": bool(video["is_favorited"])` to the template context dict.

- [ ] **Step 3: Add POST /videos/{code}/favorite endpoint**

After the `video_edit_save` function, add:

```python
@router.post("/{code}/favorite")
async def video_favorite_toggle(request: Request, code: str):
    from src.db import toggle_favorite

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        is_favorited = toggle_favorite(conn, code)
        star = "★" if is_favorited else "☆"
        return templates.TemplateResponse(request, "favorite_btn.html", {
            "code": code, "is_favorited": is_favorited, "star": star,
        })
    finally:
        conn.close()
```

- [ ] **Step 4: Add POST /videos/{code}/delete endpoint**

```python
@router.post("/{code}/delete")
async def video_delete(request: Request, code: str):
    from fastapi.responses import RedirectResponse
    from src.db import soft_delete_video

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        soft_delete_video(conn, code)
        return RedirectResponse(url="/videos", status_code=302)
    finally:
        conn.close()
```

- [ ] **Step 5: Commit**

```bash
git add src/web/routes/videos.py
git commit -m "feat: add favorite toggle, soft delete, and deleted=0 filters

- /videos list query filters WHERE deleted=0
- /videos/{code} detail joins favorites and filters deleted=0
- POST /videos/{code}/favorite toggles favorite status
- POST /videos/{code}/delete soft-deletes and redirects to /videos

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Routes — favorites list page

**Files:**
- Create: `src/web/routes/favorites.py`
- Modify: `src/web/routes/__init__.py`

- [ ] **Step 1: Create favorites route file**

Create `src/web/routes/favorites.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/favorites", dependencies=[Depends(require_auth)])

PAGE_SIZE = 20


@router.get("")
async def favorites_list(
    request: Request,
    q: str = Query(default=""),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
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
        where_clauses = ["v.deleted=0"]
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(*) as c FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at, f.created_at as fav_created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress
            FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template_name = "favorites_content.html" if request.headers.get("HX-Request") else "favorites.html"

        return templates.TemplateResponse(request, template_name, {
            "videos": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "q": q,
            "sort": sort,
            "order": order,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Register the favorites router**

In `src/web/routes/__init__.py`, add the import and include:

```python
from src.web.routes.favorites import router as favorites_router
# ...
app.include_router(favorites_router)
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/favorites.py src/web/routes/__init__.py
git commit -m "feat: add /favorites list page with full search/sort/pagination

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Routes — add deleted=0 to actress and dashboard queries

**Files:**
- Modify: `src/web/routes/actresses.py`
- Modify: `src/web/routes/dashboard.py`

- [ ] **Step 1: Update actress routes to filter deleted=0**

In `src/web/routes/actresses.py`:

For `/actresses/{name}` route (line 79-83), change the count and data queries to add `WHERE v.deleted=0`:

```python
        count = conn.execute("""
            SELECT COUNT(*) as c
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
        """, (name,)).fetchone()["c"]
```

And the data query (lines 87-93):

```python
        videos = conn.execute("""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker, v.created_at
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """.format(sort=sort, order=order), (name, PAGE_SIZE, offset)).fetchall()
```

For `/actresses/{name}/videos` route (lines 47-51):

```python
        videos = conn.execute("""
            SELECT v.code, v.title, v.score, v.date, v.cover_url
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0 ORDER BY v.date DESC
        """, (name,)).fetchall()
```

- [ ] **Step 2: Update dashboard queries to filter deleted=0**

In `src/web/routes/dashboard.py`, update the queries (lines 16-23):

```python
        total_videos = conn.execute("SELECT COUNT(*) as c FROM videos WHERE deleted=0").fetchone()["c"]
        total_actresses = conn.execute("SELECT COUNT(DISTINCT name) as c FROM actresses").fetchone()["c"]
        today_new = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE deleted=0 AND date(created_at) = date('now','localtime')"
        ).fetchone()["c"]
        missing_magnets = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE deleted=0 AND code NOT IN (SELECT DISTINCT video_code FROM magnets)"
        ).fetchone()["c"]

        recent = conn.execute(
            "SELECT code, title, score, date, created_at FROM videos WHERE deleted=0 ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        top_most_wanted = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='most_wanted' AND v.deleted=0 ORDER BY r.rank LIMIT 10"""
        ).fetchall()

        top_rated = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='top_rated' AND v.deleted=0 ORDER BY r.rank LIMIT 10"""
        ).fetchall()
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/actresses.py src/web/routes/dashboard.py
git commit -m "fix: filter deleted=0 in actress and dashboard queries

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Templates — favorite button partial + video detail page

**Files:**
- Create: `src/web/templates/favorite_btn.html`
- Modify: `src/web/templates/video_detail.html`

- [ ] **Step 1: Create favorite_btn.html partial**

Create `src/web/templates/favorite_btn.html`:

```html
<button class="fav-btn {% if is_favorited %}fav-active{% endif %}"
        hx-post="/videos/{{ code }}/favorite"
        hx-swap="outerHTML"
        style="background:none;border:none;cursor:pointer;font-size:1.2rem;padding:0 0.3rem;line-height:1;"
        title="{% if is_favorited %}Remove favorite{% else %}Add favorite{% endif %}">
    {{ star }}
</button>
```

- [ ] **Step 2: Update video_detail.html**

Modify `src/web/templates/video_detail.html`:

Replace the Edit button row (line 43-44) with favorite + edit + delete buttons:

```html
            <div class="btn-group" style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:1rem;">
                {% include "favorite_btn.html" %}
                <a href="/videos/{{ video.code }}/edit" role="button"
                   hx-get="/videos/{{ video.code }}/edit" hx-target="closest article" hx-swap="outerHTML">Edit</a>
                <button class="outline" style="color:var(--pico-del-color);border-color:var(--pico-del-color);"
                        hx-post="/videos/{{ video.code }}/delete"
                        hx-confirm="确定删除？"
                        hx-target="body">Delete</button>
            </div>
```

Replace the actress section (lines 48-56):

```html
    <h3>Actresses</h3>
    <div class="actress-list">
    {% for a in actresses %}
        <span class="actress-tag">
            {% if a.actress_id %}
            <a href="https://www.javlibrary.com/cn/vl_star.php?s={{ a.actress_id }}" target="_blank" rel="noopener" style="color:inherit;">{{ a.name }}</a>
            {% else %}
            {{ a.name }}
            {% endif %}
            <a href="/actresses/{{ a.name }}" title="View in library" style="color:inherit;font-size:0.75rem;margin-left:0.15rem;">&#128269;</a>
        </span>
    {% endfor %}
    </div>
    {% if not actresses %}<p>No actresses listed.</p>{% endif %}
```

Note: The detail route now returns `actresses` rows with `name` and `actress_id` columns from the DB, not just name strings. Update the query in the route to select both:

```python
        actresses = conn.execute(
            "SELECT name, actress_id FROM actresses WHERE video_code=? ORDER BY name", (code,)
        ).fetchall()
```

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/favorite_btn.html src/web/templates/video_detail.html src/web/routes/videos.py
git commit -m "feat: add favorite/delete buttons and actress javlibrary links on detail page

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: Templates — favorite button on video cards

**Files:**
- Modify: `src/web/templates/videos_partial.html`

- [ ] **Step 1: Add favorite star to video cards**

In `videos_partial.html`, add a favorite button in the top-right corner of each card:

```html
<div class="video-card" style="position:relative;">
    {% set fav_code = v.code %}
    {% include "favorite_btn_card.html" %}
    <a href="/videos/{{ v.code }}">
```

Wait — the favorite button on cards needs to know if this specific card is favorited. We don't have `is_favorited` in the video list query yet. Let's handle this:

First, create `src/web/templates/favorite_btn_card.html` (a simpler inline version):

```html
<button class="fav-btn-card"
        hx-post="/videos/{{ v.code }}/favorite"
        hx-swap="outerHTML"
        style="position:absolute;top:0.25rem;right:0.25rem;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.9rem;padding:0.1rem 0.3rem;line-height:1;z-index:1;"
        title="Favorite">☆</button>
```

But we need to show the correct initial state. Let's add `is_favorited` to the video list query.

In `videos.py`, update the data query to LEFT JOIN favorites and select the favorite indicator:

```python
        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress,
                   (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited
            FROM videos v
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
```

Then in `videos_partial.html`, use the `is_favorited` value to show the correct star:

```html
<button class="fav-btn-card"
        hx-post="/videos/{{ v.code }}/favorite"
        hx-swap="outerHTML"
        style="position:absolute;top:0.25rem;right:0.25rem;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.9rem;padding:0.1rem 0.3rem;line-height:1;z-index:1;"
        title="{% if v.is_favorited %}Remove favorite{% else %}Add favorite{% endif %}">{% if v.is_favorited %}★{% else %}☆{% endif %}</button>
```

Actually, using the shared `favorite_btn.html` partial for both is cleaner. The issue is the card uses `v` and the detail uses `video`. Let's make the partial generic — always use `code` and `is_favorited`:

Update `favorite_btn.html` to be used on cards too:

```html
<button class="fav-btn-card"
        hx-post="/videos/{{ code }}/favorite"
        hx-swap="outerHTML"
        style="position:absolute;top:0.25rem;right:0.25rem;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.9rem;padding:0.1rem 0.3rem;line-height:1;z-index:1;"
        title="{% if is_favorited %}Remove favorite{% else %}Add favorite{% endif %}">{% if is_favorited %}★{% else %}☆{% endif %}</button>
```

Hmm, but the styling differs between card and detail page. Let me use two separate partials:
- `favorite_btn_card.html` — card version (positioned absolute, small, translucent bg)
- `favorite_btn.html` — detail page version (inline button)

Actually, let me reconsider. The simpler approach: use a single `favorite_btn.html` that the POST endpoint returns. For the initial render, use inline conditional in each template. The POST response (favorite toggle) returns the button HTML that HTMX swaps in place.

Let me think about this more carefully. The favorite button on the card needs to:
1. Show correct initial state (☆ or ★)
2. On click, POST to /videos/{code}/favorite
3. HTMX swaps the button with the response

The favorite button on the detail page needs:
1. Same functionality
2. Different styling (inline, not absolute positioned)

The simplest design: make `favorite_btn.html` a tiny partial with just the button, and use it everywhere. The card template wraps it in a positioned container, the detail page doesn't.

Revised `favorite_btn.html`:

```html
<button hx-post="/videos/{{ code }}/favorite"
        hx-swap="outerHTML"
        class="fav-btn {% if is_favorited %}fav-active{% endif %}"
        title="{% if is_favorited %}Remove favorite{% else %}Add favorite{% endif %}">{% if is_favorited %}★{% else %}☆{% endif %}</button>
```

And in `videos_partial.html`, wrap it:

```html
<span style="position:absolute;top:0.25rem;right:0.25rem;z-index:1;">
    {% with code=v.code, is_favorited=v.is_favorited %}{% include "favorite_btn.html" %}{% endwith %}
</span>
```

In `video_detail.html`:

```html
{% with code=video.code %}{% include "favorite_btn.html" %}{% endwith %}
```

Wait, Jinja2 `{% with %}` works differently. `is_favorited` needs to be in context. When the detail route passes it, the template can use it.

Actually, in the `favorite_btn.html` partial, we don't need `with` if the variables are already in the template context. The partial has access to the parent's context.

Let me simplify. The `favorite_btn.html` partial uses `code` and `is_favorited` from the template context. The detail route passes `code` (as `video.code`) and `is_favorited`. The card template already has `v.code` and `v.is_favorited`. So we just need to set the context properly before including.

For the card, we set `code` and `is_favorited` in the template context before including. Jinja2 `{% with %}` works for this:

```django
{% with code=v.code, is_favorited=(v.is_favorited|int > 0) %}
    {% include "favorite_btn.html" %}
{% endwith %}
```

Wait, Jinja2 doesn't have the `( )` expression in `with`. Let me just inline it instead. Or I'll just pass the values directly.

Actually in Jinja2, `{% with %}` does support expressions:
```
{% with code=v.code, is_favorited=v.is_favorited %}
```

And `v.is_favorited` is an integer (0 or 1 from COUNT). In the template, `{% if is_favorited %}` treats 0 as false and 1 as true. So this should work fine.

For the detail page, the same thing but `code=video.code` and `is_favorited` is already a boolean from Python.

OK let me just write the actual plan steps now. I've been overthinking this.

Let me revise the task structure to be simpler.

For `videos_partial.html`, add the favorite button inline on each card. No need for a separate partial — just inline it:

```html
<div class="video-card" style="position:relative;">
    <span style="position:absolute;top:0.25rem;right:0.25rem;z-index:1;">
        <button hx-post="/videos/{{ v.code }}/favorite"
                hx-swap="outerHTML"
                style="background:rgba(0,0,0,0.5);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.85rem;padding:0.1rem 0.3rem;line-height:1;"
                title="{% if v.is_favorited %}Remove favorite{% else %}Add favorite{% endif %}">{% if v.is_favorited %}★{% else %}☆{% endif %}</button>
    </span>
    ...
```

For `video_detail.html`, use a separate larger button (inline with Edit/Delete).

The POST /favorite endpoint returns just the button HTML. Since the card and detail page have different button styles, the endpoint needs to know which style to return. We can use a query param or a request header.

Simpler approach: The endpoint always returns the same simple button HTML. The CSS in the parent context handles the styling. Both card and detail page use the same markup.

Hmm, but the card button has different positioning (absolute, top-right corner) vs the detail page button (inline). Let me use a query parameter:

POST `/videos/{code}/favorite?style=card` → returns card-style button
POST `/videos/{code}/favorite?style=detail` → returns detail-style button

Or even simpler: use `HX-Trigger` header detection, or just have the favorite endpoint return a generic button that's styled by its container.

Actually the simplest: always return just the star character in a styled button. The card wraps it in an absolute positioned span, the detail page doesn't. The response replaces just the button itself (hx-swap="outerHTML").

So:
- Card button: `<span style="position:absolute;..."><button ...>☆</button></span>` — hx-post targets the button, swaps the button
- Detail button: `<button ...>☆</button>` — same

Wait, but if the card wraps the button in a span, the hx-post is on the button and hx-swap="outerHTML" replaces just the button. The span is not replaced. That's fine — the span is just for positioning.

OK this is getting too detailed. Let me just write the plan with concrete steps and CSS classes instead of inline styles. I'll use a CSS class for the card favorite button and another for the detail page.

Let me restart writing the plan in a cleaner way. I'll use fewer, slightly larger tasks and focus on clear, concrete steps.<｜end▁of▁thinking｜>Let me write the full plan now. I've analyzed all files and test fixtures.

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="Write">
<｜｜DSML｜｜parameter name="content" string="true"># Favorites, Delete & Actress Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add video favorites (toggle on cards + detail), soft delete, favorites list page, and javlibrary actress links on detail page.

**Architecture:** New `favorites` table + `deleted`/`deleted_at` columns on videos + `actress_id` on actresses. Two new endpoints (POST favorite toggle, POST delete). New `/favorites` page reusing the videos grid pattern. Scraper updated to extract actress IDs from detail page hrefs.

**Tech Stack:** FastAPI, Jinja2, HTMX 2.0, Pico CSS, SQLite

---

### Task 1: Database — add tables, columns, and helpers

**Files:**
- Modify: `src/db.py`

- [ ] **Step 1: Add favorites table to init_db()**

In `src/db.py`, inside `init_db()`'s `conn.executescript()`, add after the magnets table DDL (line 61):

```sql
        CREATE TABLE IF NOT EXISTS favorites (
            video_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (video_code) REFERENCES videos(code) ON DELETE CASCADE
        );
```

- [ ] **Step 2: Add migration blocks for new columns**

After the existing magnet metadata migration block (line 73), add:

```python
    # Migration: soft-delete columns on videos
    for col in [("deleted", "INTEGER NOT NULL DEFAULT 0"), ("deleted_at", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col[0]} {col[1]}")
        except sqlite3.OperationalError:
            pass

    # Migration: actress_id on actresses
    try:
        conn.execute("ALTER TABLE actresses ADD COLUMN actress_id TEXT")
    except sqlite3.OperationalError:
        pass
```

- [ ] **Step 3: Update save_actresses() to accept both str and (name, actress_id) tuples**

Replace the function body (lines 113-121):

```python
def save_actresses(conn, video_code, actresses):
    conn.execute("DELETE FROM actresses WHERE video_code=?", (video_code,))
    for item in actresses:
        if isinstance(item, str):
            name, actress_id = item.strip(), None
        else:
            name = item[0].strip()
            actress_id = item[1] if len(item) > 1 and item[1] else None
        if name:
            conn.execute(
                "INSERT INTO actresses (video_code, name, actress_id) VALUES (?, ?, ?)",
                (video_code, name, actress_id)
            )
    conn.commit()
```

- [ ] **Step 4: Add toggle_favorite() and soft_delete_video()**

After `save_actresses()`, add two new functions:

```python
def toggle_favorite(conn, video_code):
    """Toggle favorite status. Returns new state (True=favorited, False=unfavorited)."""
    row = conn.execute(
        "SELECT video_code FROM favorites WHERE video_code=?", (video_code,)
    ).fetchone()
    if row:
        conn.execute("DELETE FROM favorites WHERE video_code=?", (video_code,))
        conn.commit()
        return False
    conn.execute("INSERT INTO favorites (video_code) VALUES (?)", (video_code,))
    conn.commit()
    return True


def soft_delete_video(conn, video_code):
    """Soft-delete a video by setting deleted=1."""
    conn.execute(
        "UPDATE videos SET deleted=1, deleted_at=datetime('now','localtime'), "
        "updated_at=datetime('now','localtime') WHERE code=?",
        (video_code,)
    )
    conn.commit()
```

- [ ] **Step 5: Run db tests to verify no regressions**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_db.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/db.py
git commit -m "feat: add favorites table, soft-delete columns, actress_id, and helpers

- Add favorites table to init_db schema
- Add deleted/deleted_at columns on videos (migration)
- Add actress_id column on actresses (migration)
- Update save_actresses to accept str or (name, actress_id) tuples
- Add toggle_favorite() and soft_delete_video()

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Scraper — extract actress ID from detail page hrefs

**Files:**
- Modify: `src/scraper.py`
- Modify: `tests/test_scraper.py`
- Create: `tests/fixtures/video_detail.html`

- [ ] **Step 1: Update parse_detail_page() to extract actress_id**

In `src/scraper.py`, replace the actress extraction block (lines 184-188):

```python
    actresses = []
    for a_el in soup.select("#video_cast .cast .star a[href*=vl_star]"):
        name = a_el.text.strip()
        if not name:
            continue
        href = a_el.get("href", "")
        m = re.search(r's=(\w+)', href)
        actress_id = m.group(1) if m else ""
        actresses.append((name, actress_id))
```

- [ ] **Step 2: Create test fixture for detail page with actress links**

Create `tests/fixtures/video_detail.html`:

```html
<!DOCTYPE html>
<html>
<body>
<div id="video_date"><table><tr><td class="text">2024-06-15</td></tr></table></div>
<div id="video_length"><table><tr><td><span class="text">120</span></td></tr></table></div>
<div id="video_maker"><table><tr><td class="text"><a href="/m.php?id=1">Studio X</a></td></tr></table></div>
<div id="video_label"><table><tr><td class="text"><a href="/l.php?id=2">Label Y</a></td></tr></table></div>
<div id="video_cast" class="item">
    <table><tr>
    <td class="text">
        <span class="cast"><span class="star"><a href="vl_star.php?s=aaa111" rel="tag">Actress One</a></span></span>
        <span class="cast"><span class="star"><a href="vl_star.php?s=bbb222" rel="tag">Actress Two</a></span></span>
    </td>
    </tr></table>
</div>
<div class="score">(8.52)</div>
<img id="video_jacket_img" src="//pics.javlibrary.com/abc-123.jpg">
</body>
</html>
```

- [ ] **Step 3: Update test_extracts_all_fields assertion for new actress format**

In `tests/test_scraper.py`, line 105, change:

```python
        assert result["actresses"] == ["Actress One", "Actress Two"]
```
To:
```python
        assert result["actresses"] == [("Actress One", "aaa111"), ("Actress Two", "bbb222")]
```

Also add a new test in `TestParseDetailPageEdgeCases`:

```python
    def test_actress_with_href_id(self):
        html = """
        <div id="video_cast">
            <span class="cast"><span class="star"><a href="vl_star.php?s=xyz789" rel="tag">With ID</a></span></span>
        </div>
        """
        result = parse_detail_page(html)
        assert result["actresses"] == [("With ID", "xyz789")]
```

- [ ] **Step 4: Run scraper tests**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_scraper.py -v
```

Expected: all tests pass, including the new one.

- [ ] **Step 5: Commit**

```bash
git add src/scraper.py tests/fixtures/video_detail.html tests/test_scraper.py
git commit -m "feat: extract actress ID from javlibrary detail page hrefs

parse_detail_page now returns (name, actress_id) tuples.
Verified against live_video_detail.html fixture structure:
  #video_cast .cast .star a[href*=vl_star]

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Routes — favorite toggle, delete, deleted=0 filter

**Files:**
- Modify: `src/web/routes/videos.py`

- [ ] **Step 1: Add deleted=0 filter to video_list query**

In `videos.py` line 32, add `v.deleted=0` as the base where clause:

```python
        where_clauses = ["v.deleted=0"]
        params = []
```

- [ ] **Step 2: Update video_detail to filter deleted=0, join favorites, select actress_id**

Replace the detail route query and context (lines 84-101):

```python
        video = conn.execute(
            "SELECT v.*, (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited "
            "FROM videos v WHERE v.code=? AND v.deleted=0", (code,)
        ).fetchone()
        if not video:
            return templates.TemplateResponse(request, "404.html", status_code=404)

        actresses = conn.execute(
            "SELECT name, actress_id FROM actresses WHERE video_code=? ORDER BY name", (code,)
        ).fetchall()

        magnets = conn.execute(
            "SELECT magnet, source, title, size, magnet_date, download_count, created_at "
            "FROM magnets WHERE video_code=? ORDER BY created_at DESC", (code,)
        ).fetchall()

        rankings = conn.execute(
            "SELECT list_type, rank FROM rankings WHERE video_code=?", (code,)
        ).fetchall()

        return templates.TemplateResponse(request, "video_detail.html", {
            "video": video,
            "is_favorited": bool(video["is_favorited"]),
            "actresses": actresses,
            "magnets": magnets,
            "rankings": rankings,
        })
```

- [ ] **Step 3: Update video_list to include favorite state for each video**

Replace the data query (lines 51-59):

```python
        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress,
                   (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited
            FROM videos v
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
```

- [ ] **Step 4: Add POST /videos/{code}/favorite endpoint**

After the existing `video_edit_save` function, add:

```python
@router.post("/{code}/favorite")
async def video_favorite_toggle(request: Request, code: str):
    from src.db import toggle_favorite

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        is_favorited = toggle_favorite(conn, code)
        return templates.TemplateResponse(request, "favorite_btn.html", {
            "code": code,
            "is_favorited": is_favorited,
        })
    finally:
        conn.close()
```

- [ ] **Step 5: Add POST /videos/{code}/delete endpoint**

```python
@router.post("/{code}/delete")
async def video_delete(code: str):
    from fastapi.responses import RedirectResponse
    from src.db import soft_delete_video

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        soft_delete_video(conn, code)
        return RedirectResponse(url="/videos", status_code=302)
    finally:
        conn.close()
```

- [ ] **Step 6: Also update video_edit_save to include is_favorited and actress_id in context**

After the edit save at lines 153-167, the re-render of video_detail needs the updated queries. In the HTMX path (line 155-157), update actresses query:

```python
            actresses = conn.execute(
                "SELECT name, actress_id FROM actresses WHERE video_code=? ORDER BY name", (code,)
            ).fetchall()
```

And add `is_favorited` to the template context:

```python
            fav_row = conn.execute(
                "SELECT COUNT(*) as c FROM favorites WHERE video_code=?", (code,)
            ).fetchone()
            is_favorited = bool(fav_row["c"])
```

Then pass it: `"is_favorited": is_favorited`.

- [ ] **Step 7: Run web tests**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_web.py -v -k "not test_trigger"
```

Expected: all non-task tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/web/routes/videos.py
git commit -m "feat: add favorite toggle, delete endpoints, and deleted=0 filters

- /videos list filters WHERE v.deleted=0 and includes is_favorited
- /videos/{code} detail filters deleted=0, joins favorites, selects actress_id
- POST /videos/{code}/favorite toggles and returns favorite_btn.html partial
- POST /videos/{code}/delete soft-deletes with redirect to /videos

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Routes — favorites list page + register router

**Files:**
- Create: `src/web/routes/favorites.py`
- Modify: `src/web/routes/__init__.py`

- [ ] **Step 1: Create favorites route**

Create `src/web/routes/favorites.py`:

```python
import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/favorites", dependencies=[Depends(require_auth)])

PAGE_SIZE = 20


@router.get("")
async def favorites_list(
    request: Request,
    q: str = Query(default=""),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
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
        where_clauses = ["v.deleted=0"]
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(*) as c FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress,
                   1 as is_favorited
            FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template_name = "favorites_content.html" if request.headers.get("HX-Request") else "favorites.html"

        return templates.TemplateResponse(request, template_name, {
            "videos": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "q": q,
            "sort": sort,
            "order": order,
        })
    finally:
        conn.close()
```

- [ ] **Step 2: Register router in __init__.py**

In `src/web/routes/__init__.py`, add:

```python
    from src.web.routes.favorites import router as favorites_router
    # ...
    app.include_router(favorites_router)
```

After the actresses_router include.

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/favorites.py src/web/routes/__init__.py
git commit -m "feat: add /favorites page with full search/sort/pagination

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Routes — filter deleted=0 in actress and dashboard queries

**Files:**
- Modify: `src/web/routes/actresses.py`
- Modify: `src/web/routes/dashboard.py`

- [ ] **Step 1: Add WHERE v.deleted=0 to all actress queries**

In `src/web/routes/actresses.py`:

Line 47-51 (`/actresses/{name}/videos`):
```python
        videos = conn.execute("""
            SELECT v.code, v.title, v.score, v.date, v.cover_url
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0 ORDER BY v.date DESC
        """, (name,)).fetchall()
```

Lines 79-83 (count query in `/actresses/{name}`):
```python
        count = conn.execute("""
            SELECT COUNT(*) as c
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
        """, (name,)).fetchone()["c"]
```

Lines 87-93 (data query in `/actresses/{name}`):
```python
        videos = conn.execute("""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker, v.created_at
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """.format(sort=sort, order=order), (name, PAGE_SIZE, offset)).fetchall()
```

- [ ] **Step 2: Add WHERE deleted=0 to all dashboard queries**

In `src/web/routes/dashboard.py`, update every query that reads from videos:

```python
        total_videos = conn.execute("SELECT COUNT(*) as c FROM videos WHERE deleted=0").fetchone()["c"]
        today_new = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE deleted=0 AND date(created_at) = date('now','localtime')"
        ).fetchone()["c"]
        missing_magnets = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE deleted=0 AND code NOT IN (SELECT DISTINCT video_code FROM magnets)"
        ).fetchone()["c"]
        recent = conn.execute(
            "SELECT code, title, score, date, created_at FROM videos WHERE deleted=0 ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        top_most_wanted = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='most_wanted' AND v.deleted=0 ORDER BY r.rank LIMIT 10"""
        ).fetchall()
        top_rated = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='top_rated' AND v.deleted=0 ORDER BY r.rank LIMIT 10"""
        ).fetchall()
```

- [ ] **Step 3: Run web tests to verify no regressions**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_web.py -v -k "not test_trigger"
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/web/routes/actresses.py src/web/routes/dashboard.py
git commit -m "fix: filter deleted=0 in actress and dashboard queries

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Templates — favorite button partial, video detail, video cards

**Files:**
- Create: `src/web/templates/favorite_btn.html`
- Modify: `src/web/templates/video_detail.html`
- Modify: `src/web/templates/videos_partial.html`
- Modify: `src/web/templates/videos_content.html`

- [ ] **Step 1: Create favorite_btn.html partial**

Create `src/web/templates/favorite_btn.html`:

```html
<button hx-post="/videos/{{ code }}/favorite"
        hx-swap="outerHTML"
        class="fav-btn {% if is_favorited %}fav-active{% endif %}"
        title="{% if is_favorited %}Remove favorite{% else %}Add favorite{% endif %}"
        style="background:none;border:none;cursor:pointer;font-size:1.2rem;padding:0 0.2rem;line-height:1;">{% if is_favorited %}★{% else %}☆{% endif %}</button>
```

- [ ] **Step 2: Update video_detail.html — add buttons and actress links**

**Buttons block** — replace the Edit button (line 43-44):

```html
            <div class="btn-group" style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:1rem;">
                {% include "favorite_btn.html" %}
                <a href="/videos/{{ video.code }}/edit" role="button"
                   hx-get="/videos/{{ video.code }}/edit" hx-target="closest article" hx-swap="outerHTML">Edit</a>
                <button class="outline" style="color:var(--pico-del-color);border-color:var(--pico-del-color);"
                        hx-post="/videos/{{ video.code }}/delete"
                        hx-confirm="确定删除？"
                        hx-target="body">Delete</button>
            </div>
```

**Actresses block** — replace lines 48-56:

```html
    <h3>Actresses</h3>
    <div class="actress-list">
    {% for a in actresses %}
        <span class="actress-tag">
            {% if a.actress_id %}
            <a href="https://www.javlibrary.com/cn/vl_star.php?s={{ a.actress_id }}" target="_blank" rel="noopener" style="color:inherit;">{{ a.name }}</a>
            {% else %}
            {{ a.name }}
            {% endif %}
            <a href="/actresses/{{ a.name }}" title="View in library" style="color:inherit;font-size:0.75rem;margin-left:0.15rem;text-decoration:none;">&#128269;</a>
        </span>
    {% endfor %}
    </div>
    {% if not actresses %}<p>No actresses listed.</p>{% endif %}
```

Note: For the favorite_btn.html include on detail page, `code` is `{{ video.code }}` and `is_favorited` is passed from the route. Need to confirm context variables match. Add this context setup before the include:

```html
            {% with code=video.code %}{% include "favorite_btn.html" %}{% endwith %}
```

But `is_favorited` needs to be in the template context too — it's already passed by the route.

- [ ] **Step 3: Update videos_partial.html — add favorite button on cards**

Add a positioned favorite button on each card. The card div becomes:

```html
<div class="video-card" style="position:relative;">
    <span style="position:absolute;top:0.25rem;right:0.25rem;z-index:2;">
        {% with code=v.code, is_favorited=v.is_favorited %}{% include "favorite_btn.html" %}{% endwith %}
    </span>
    <a href="/videos/{{ v.code }}">
        {% if v.cover_url %}
        <img src="{{ v.cover_url }}" alt="{{ v.code }}" loading="lazy">
        {% else %}
        <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 2 3'/>" alt="no cover">
        {% endif %}
    </a>
    ...
</div>
```

Note: Jinja2 `{% with %}` with multiple variables. The `v.is_favorited` from the query is an integer (0 or 1 from COUNT(*)). In Jinja2, `{% if 0 %}` is falsy and `{% if 1 %}` is truthy, so the partial's `{% if is_favorited %}` works correctly.

- [ ] **Step 4: Update videos_content.html — include favorite_btn.html for search bar area**

No changes needed to `videos_content.html` — the favorite button is in `videos_partial.html` which is already included.

- [ ] **Step 5: Commit**

```bash
git add src/web/templates/favorite_btn.html src/web/templates/video_detail.html src/web/templates/videos_partial.html
git commit -m "feat: add favorite button on cards and detail page, actress javlibrary links

- favorite_btn.html partial reused across card and detail page
- Cards show ☆/★ in top-right corner with HTMX toggle
- Detail page shows favorite button next to Edit and Delete
- Actress tags link to javlibrary when actress_id is available
- Search icon links to internal /actresses/{name}

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: Templates — favorites page + sidebar link

**Files:**
- Create: `src/web/templates/favorites.html`
- Create: `src/web/templates/favorites_content.html`
- Modify: `src/web/templates/base.html`

- [ ] **Step 1: Create favorites.html**

Create `src/web/templates/favorites.html`:

```html
{% extends "base.html" %}
{% block title %}Favorites{% endblock %}
{% block content %}
{% include "favorites_content.html" %}
{% endblock %}
```

- [ ] **Step 2: Create favorites_content.html**

Create `src/web/templates/favorites_content.html`:

```html
<h2>Favorites ({{ total }})</h2>

<div style="display:flex; gap:1rem; margin-bottom:1rem; flex-wrap:wrap;">
    <form hx-get="/favorites" hx-target="#main" hx-push-url="true" style="display:flex; gap:0.5rem; align-items:end; flex-wrap:wrap;">
        <input type="hidden" name="q" value="{{ q }}">
        <label>Sort
            <select name="sort" onchange="this.form.dispatchEvent(new Event('submit',{bubbles:true}))">
                <option value="created_at" {% if sort=='created_at' %}selected{% endif %}>Added</option>
                <option value="date" {% if sort=='date' %}selected{% endif %}>Release Date</option>
                <option value="score" {% if sort=='score' %}selected{% endif %}>Score</option>
                <option value="code" {% if sort=='code' %}selected{% endif %}>Code</option>
                <option value="title" {% if sort=='title' %}selected{% endif %}>Title</option>
            </select>
        </label>
        <label>Order
            <select name="order" onchange="this.form.dispatchEvent(new Event('submit',{bubbles:true}))">
                <option value="desc" {% if order=='desc' %}selected{% endif %}>Desc</option>
                <option value="asc" {% if order=='asc' %}selected{% endif %}>Asc</option>
            </select>
        </label>
        <noscript><button type="submit">Apply</button></noscript>
    </form>
</div>

{% if total == 0 %}
<p>No favorites yet. Browse <a href="/videos">videos</a> to add some.</p>
{% else %}
{% include "videos_partial.html" %}
{% endif %}
```

- [ ] **Step 3: Add Favorites link to sidebar in base.html**

In `src/web/templates/base.html`, add the Favorites link in the sidebar nav after Videos (line 45):

```html
            <a href="/favorites" hx-get="/favorites" hx-target="#main" hx-push-url="true">Favorites</a>
```

Place it after the Actresses link for logical grouping:

```html
            <a href="/videos" hx-get="/videos" hx-target="#main" hx-push-url="true">Videos</a>
            <a href="/actresses" hx-get="/actresses" hx-target="#main" hx-push-url="true">Actresses</a>
            <a href="/favorites" hx-get="/favorites" hx-target="#main" hx-push-url="true">Favorites</a>
            <a href="/tasks" hx-get="/tasks" hx-target="#main" hx-push-url="true">Tasks</a>
```

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/favorites.html src/web/templates/favorites_content.html src/web/templates/base.html
git commit -m "feat: add favorites list page and sidebar link

- favorites.html extends base, favorites_content.html for HTMX
- Reuses videos_partial.html grid with search/sort/pagination
- Empty state with link to browse videos
- Sidebar Favorites link between Actresses and Tasks

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: Web tests — add tests for new endpoints

**Files:**
- Modify: `tests/test_web.py`

- [ ] **Step 1: Add test for favorite toggle**

Add to `TestVideos` class:

```python
    def test_favorite_toggle(self, auth_client):
        resp = auth_client.post("/videos/TEST-001/favorite")
        assert resp.status_code == 200
        assert "★" in resp.text
        # Toggle back
        resp = auth_client.post("/videos/TEST-001/favorite")
        assert resp.status_code == 200
        assert "☆" in resp.text

    def test_favorite_appears_on_detail(self, auth_client):
        auth_client.post("/videos/TEST-001/favorite")  # favorite it
        resp = auth_client.get("/videos/TEST-001")
        assert "★" in resp.text

    def test_video_delete_redirects(self, auth_client):
        resp = auth_client.post("/videos/TEST-003/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/videos"

    def test_deleted_video_not_in_list(self, auth_client):
        auth_client.post("/videos/TEST-003/delete")
        resp = auth_client.get("/videos")
        assert "TEST-003" not in resp.text

    def test_deleted_video_returns_404(self, auth_client):
        auth_client.post("/videos/TEST-002/delete")
        resp = auth_client.get("/videos/TEST-002")
        assert resp.status_code == 404
```

- [ ] **Step 2: Add test class for Favorites**

```python
class TestFavorites:
    def test_favorites_page_returns_200(self, auth_client):
        resp = auth_client.get("/favorites")
        assert resp.status_code == 200

    def test_favorites_empty_state(self, auth_client):
        resp = auth_client.get("/favorites")
        assert "No favorites yet" in resp.text

    def test_favorites_shows_favorited(self, auth_client):
        auth_client.post("/videos/TEST-001/favorite")
        resp = auth_client.get("/favorites")
        assert "TEST-001" in resp.text
        assert "TEST-002" not in resp.text

    def test_favorites_htmx_returns_content(self, auth_client):
        resp = auth_client.get("/favorites", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "favorites_content.html" not in resp.text  # should render, not show filename
```

- [ ] **Step 3: Add test for actress_id on detail page**

```python
    def test_video_detail_shows_actress_jav_link(self, auth_client):
        # Insert an actress with actress_id
        from src.db import save_actresses
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        save_actresses(conn, "TEST-001", [("Alice", "alice123")])
        conn.close()

        resp = auth_client.get("/videos/TEST-001")
        assert "vl_star.php?s=alice123" in resp.text
```

- [ ] **Step 4: Run all web tests**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/test_web.py -v -k "not test_trigger"
```

Expected: all tests pass including new ones.

- [ ] **Step 5: Commit**

```bash
git add tests/test_web.py
git commit -m "test: add tests for favorite toggle, soft delete, favorites page

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: Final integration verification

- [ ] **Step 1: Run full test suite**

```bash
cd /home/node/playground/jav_ext && python -m pytest tests/ -v -k "not live and not test_trigger"
```

Expected: all tests pass. Fix any failures.

- [ ] **Step 2: Verify app starts and serves pages**

```bash
cd /home/node/playground/jav_ext && timeout 5 python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8081 2>&1 || true
```

Expected: no import errors or startup failures.

- [ ] **Step 3: Commit any fixups**

```bash
git add -u && git commit -m "fix: integration fixes for favorites/delete features"
```
(only if changes were needed)
