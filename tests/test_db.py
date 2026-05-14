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
