# JAV Panel: Favorites, Delete & Actress Links

## Context

The web panel currently supports browsing, searching, and filtering videos but lacks personal curation features. Users want to bookmark interesting videos, remove unwanted ones, and jump to javlibrary actress pages directly.

## Database Changes

### New table: favorites
```sql
CREATE TABLE IF NOT EXISTS favorites (
    video_code TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (video_code) REFERENCES videos(code) ON DELETE CASCADE
);
```

### New columns on existing tables
```sql
ALTER TABLE videos ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE videos ADD COLUMN deleted_at TEXT;
ALTER TABLE actresses ADD COLUMN actress_id TEXT;
```

### Soft delete
- `deleted=0` for active, `deleted=1` for deleted
- All queries that list videos filter `WHERE deleted=0`
- Cascade: actresses/magnets/rankings/favorites persist (soft delete)

## Routes

### Favorite toggle
`POST /videos/{code}/favorite`
- If favorited: DELETE FROM favorites, return unfilled-star button
- If not: INSERT INTO favorites, return filled-star button
- HTMX swaps the button element

### Delete
`POST /videos/{code}/delete`
- Sets `deleted=1, deleted_at=now()`
- Redirects to `/videos`

### Favorites list
`GET /favorites`
- Full search/sort/pagination like /videos
- Joins videos + favorites, WHERE deleted=0
- HTMX support: `favorites.html` extends base, `favorites_content.html` for HX-Request
- Reuses `videos_partial.html` for card grid

## Existing Route Changes

- `/videos`, `/videos/{code}`, `/actresses/{name}` all add `WHERE v.deleted=0`
- `/videos/{code}` joins favorites to determine initial favorite state

## Scraper Changes

`parse_detail_page()` (src/scraper.py): extract actress ID from href:
```python
# href format: vl_star.php?s=aatd6
m = re.search(r's=(\w+)', href)
actress_id = m.group(1) if m else ""
```
Return `actresses` as `[(name, actress_id), ...]` instead of `[name, ...]`.

`save_actresses()` (src/db.py): update to accept both `str` (list page, no ID) and `(name, actress_id)` tuple (detail page). Store `actress_id` when provided, NULL otherwise.

`parse_list_page()` (src/scraper.py): no change, returns `["Name1", "Name2"]`.

`parse_detail_page()` (src/scraper.py): returns `[("Name1", "id1"), ("Name2", "id2")]`.

`main.py` scrape_all(): pass through from both parse functions. Detail scraping overwrites actresses with IDs via upsert (DELETE + INSERT pattern in save_actresses).

## Templates

### New files
- `favorites.html` — extends base, includes favorites_content.html
- `favorites_content.html` — search/sort/pagination controls + videos_partial.html

### Modified files
- `video_detail.html` — favorite button (star toggle), delete button (red outline + confirm), actress javlibrary links
- `videos_partial.html` — favorite star button on each card corner
- `base.html` — sidebar "Favorites" link

## UI Details

- Favorite button: ☆ (unfavorited) / ★ (favorited), HTMX POST swaps button
- Delete button: detail page only, red outline, `confirm("确定删除？")` before POST
- Actress links: if actress_id exists, link to `https://www.javlibrary.com/cn/vl_star.php?s={actress_id}` (new tab); if not, plain text. Keep internal `/actresses/{name}` link as a secondary icon.
- Empty favorites: "No favorites yet" message
