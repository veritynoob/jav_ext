# JAV Detail Page Scraping & UI Rework

## Overview

Rework the scraper to fetch full video metadata from JavLibrary detail pages, and refresh the web panel UI with a grid layout for videos and a simplified sidebar.

## Scraper Changes

### New: `parse_detail_page(html)`

Parse a JavLibrary video detail page, extracting:

| Field | Notes |
|-------|-------|
| date | Release date |
| duration | Video length |
| maker | Studio/manufacturer |
| label | Label/brand |
| score | Numeric rating |
| actresses | All listed performer names |
| cover_url | High-resolution jacket image from `#video_jacket_img` |

### Modified: `parse_list_page(html)`

Additionally extract the `href` from each video item's `<a>` tag to get the detail page URL. No need to construct URLs manually.

### Modified: Scraping flow in `main.py`

```
scrape_list(url)
  → parse_list_page(html) → items [{code, title, cover_url, detail_url, ...}, ...]
  → for each item:
      random_delay(WAIT_MIN, WAIT_MAX)
      detail_html = load_with_cf_bypass(detail_url, ...)
      detail = parse_detail_page(detail_html)
      merge(item, detail) → upsert_video + save_actresses + download_cover
```

- A video is only inserted/updated after its detail page succeeds. Failed detail fetches are skipped with a log warning.
- After N consecutive failures, abort the run and print a summary (succeeded / skipped / failed).

### Config changes

```python
# Replace PAGE_INTERVAL_MIN / PAGE_INTERVAL_MAX
WAIT_MIN = int(os.environ.get("JAV_WAIT_MIN", "5"))
WAIT_MAX = int(os.environ.get("JAV_WAIT_MAX", "15"))

WAIT_DELAY = int(os.environ.get("JAV_WAIT_DELAY", "40"))  # CF bypass wait, unchanged
```

### Backfill

No backfill. Delete the existing database and re-scrape from scratch.

### Error handling

- Single item detail failure: log, skip, continue
- Consecutive failures (default threshold: 5): abort with summary
- CF bypass failure: retry up to `REQUEST_RETRIES` (3) times, consistent with current logic

## Web Panel Changes

### Video list: table → grid

Replace the `<table>` in `videos_partial.html` with a CSS Grid of cards:

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│                 │  │                 │  │                 │
│    Cover Image  │  │    Cover Image  │  │    Cover Image  │
│                 │  │                 │  │                 │
│ ABC-123         │  │ DEF-456         │  │ GHI-789         │
│ Title text...   │  │ Title text...   │  │ Title text...   │
│ ★ 8.5  2024-06 │  │ ★ 7.2  2023-12 │  │ ★ 6.8  2024-01 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

Each card renders: cover image, code, title (truncated), score, release date.

### Sidebar: remove links

Remove Dashboard and Magnets links from the sidebar navigation. The dashboard page and route remain (it is the homepage `/`), but it's no longer a sidebar entry.

### Magnets page: remove route

Remove the `/magnets` route registration from `routes/__init__.py`. The template file stays on disk.

### Actresses: add empty state

Add `{% else %}` clause in `actresses.html` showing a "No actresses found" message when the list is empty.

## Files Changed

| File | Change |
|------|--------|
| `src/scraper.py` | Add `parse_detail_page()`; update `parse_list_page()` to extract detail URL |
| `src/main.py` | Rework scrape loop: list → detail → merge; add abort-on-consecutive-failures; update config imports |
| `src/config.py` | Replace `PAGE_INTERVAL_MIN/MAX` with `WAIT_MIN/MAX` |
| `src/web/templates/videos_partial.html` | Rewrite as CSS grid (was table) |
| `src/web/templates/base.html` | Remove Dashboard and Magnets sidebar links |
| `src/web/templates/actresses.html` | Add empty state message |
| `src/web/routes/__init__.py` | Remove magnets router registration |
