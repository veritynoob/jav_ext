import os
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import get_db_path, init_db


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
    from src.db import upsert_video
    upsert_video(conn, video)

    row = conn.execute("SELECT * FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row is not None
    assert row["title"] == "Test Title"
    assert row["score"] == 4.5


def test_upsert_video_updates_existing(conn):
    from src.db import upsert_video
    upsert_video(conn, {"code": "ABC-001", "title": "Title 1"})
    upsert_video(conn, {"code": "ABC-001", "title": "Title 2"})

    row = conn.execute("SELECT * FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["title"] == "Title 2"


def test_save_rankings(conn):
    from src.db import upsert_video, save_rankings
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
    from src.db import upsert_video, save_rankings
    upsert_video(conn, {"code": "ABC-001"})
    save_rankings(conn, "most_wanted", [("ABC-001", "most_wanted", 1)])
    save_rankings(conn, "most_wanted", [("ABC-001", "most_wanted", 5)])

    rows = conn.execute(
        "SELECT rank FROM rankings WHERE list_type='most_wanted'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["rank"] == 5


def test_save_actresses(conn):
    from src.db import upsert_video, save_actresses
    upsert_video(conn, {"code": "ABC-001"})
    save_actresses(conn, "ABC-001", ["Alice", "Bob"])

    rows = conn.execute(
        "SELECT name FROM actresses WHERE video_code='ABC-001' ORDER BY name"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"
    assert rows[1]["name"] == "Bob"


def test_save_actresses_replaces_old(conn):
    from src.db import upsert_video, save_actresses
    upsert_video(conn, {"code": "ABC-001"})
    save_actresses(conn, "ABC-001", ["Alice"])
    save_actresses(conn, "ABC-001", ["Charlie"])

    rows = conn.execute(
        "SELECT name FROM actresses WHERE video_code='ABC-001'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["name"] == "Charlie"


def test_save_magnets(conn):
    from src.db import upsert_video, save_magnets
    upsert_video(conn, {"code": "ABC-001"})
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA", "magnet:?xt=urn:btih:BBB"])

    rows = conn.execute(
        "SELECT magnet FROM magnets WHERE video_code='ABC-001' ORDER BY magnet"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["magnet"] == "magnet:?xt=urn:btih:AAA"


def test_save_magnets_ignores_duplicate(conn):
    from src.db import upsert_video, save_magnets
    upsert_video(conn, {"code": "ABC-001"})
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA"])
    save_magnets(conn, "ABC-001", ["magnet:?xt=urn:btih:AAA"])

    rows = conn.execute(
        "SELECT magnet FROM magnets WHERE video_code='ABC-001'"
    ).fetchall()
    assert len(rows) == 1


def test_get_videos_missing_magnets(conn):
    from src.db import upsert_video, save_magnets, get_videos_missing_magnets
    from datetime import date, timedelta
    today = date.today().isoformat()
    recent = (date.today() - timedelta(days=10)).isoformat()
    upsert_video(conn, {"code": "OLD-001", "date": recent})
    upsert_video(conn, {"code": "NEW-001", "date": today})
    save_magnets(conn, "OLD-001", ["magnet:?xt=urn:btih:AAA"])

    result = get_videos_missing_magnets(conn, days=60, limit=20)
    assert len(result) == 1
    assert result[0] == "NEW-001"


def test_update_video_search_url(conn):
    from src.db import upsert_video, update_video_search_url
    upsert_video(conn, {"code": "ABC-001"})
    update_video_search_url(conn, "ABC-001", "https://clg55.top/search/ABC-001")

    row = conn.execute("SELECT search_url FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["search_url"] == "https://clg55.top/search/ABC-001"


def test_update_video_cover_path(conn):
    from src.db import upsert_video, update_video_cover_path
    upsert_video(conn, {"code": "ABC-001"})
    update_video_cover_path(conn, "ABC-001", "covers/ABC-001.jpg")

    row = conn.execute("SELECT cover_path FROM videos WHERE code=?", ("ABC-001",)).fetchone()
    assert row["cover_path"] == "covers/ABC-001.jpg"
