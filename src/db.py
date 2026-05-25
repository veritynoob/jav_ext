import os
import sqlite3
from src.config import DATA_DIR


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
            detail_url TEXT,
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

        CREATE TABLE IF NOT EXISTS favorites (
            video_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (video_code) REFERENCES videos(code) ON DELETE CASCADE
        );
    """)
    # Add detail_url column if it doesn't exist (migration for existing DBs)
    try:
        conn.execute("ALTER TABLE videos ADD COLUMN detail_url TEXT")
    except sqlite3.OperationalError:
        pass
    # Migrations for magnet metadata columns
    for col in [("title", "TEXT"), ("size", "TEXT"), ("magnet_date", "TEXT"), ("download_count", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE magnets ADD COLUMN {col[0]} {col[1]}")
        except sqlite3.OperationalError:
            pass

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

    conn.commit()
    return conn


def upsert_video(conn, video):
    conn.execute("""
        INSERT INTO videos (code, title, cover_url, detail_url, date, duration, maker, label, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            title=COALESCE(NULLIF(excluded.title, ''), videos.title),
            cover_url=COALESCE(NULLIF(excluded.cover_url, ''), videos.cover_url),
            detail_url=COALESCE(NULLIF(excluded.detail_url, ''), videos.detail_url),
            date=COALESCE(NULLIF(excluded.date, ''), videos.date),
            duration=COALESCE(NULLIF(excluded.duration, ''), videos.duration),
            maker=COALESCE(NULLIF(excluded.maker, ''), videos.maker),
            label=COALESCE(NULLIF(excluded.label, ''), videos.label),
            score=COALESCE(NULLIF(excluded.score, 0), videos.score),
            updated_at=datetime('now','localtime')
    """, (
        video.get("code"), video.get("title"), video.get("cover_url"),
        video.get("detail_url"),
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


def save_magnets(conn, video_code, magnets):
    for m in magnets:
        magnet = m.get("magnet", "").strip() if isinstance(m, dict) else m.strip()
        if not magnet:
            continue
        title = m.get("title", "") if isinstance(m, dict) else ""
        size = m.get("size", "") if isinstance(m, dict) else ""
        magnet_date = m.get("magnet_date", "") if isinstance(m, dict) else ""
        download_count = m.get("download_count", "") if isinstance(m, dict) else ""
        conn.execute(
            "INSERT OR IGNORE INTO magnets (video_code, magnet, source, title, size, magnet_date, download_count) "
            "VALUES (?, ?, 'clg55', ?, ?, ?, ?)",
            (video_code, magnet, title, size, magnet_date, download_count)
        )
    conn.commit()


def has_video_detail(conn, code):
    """Return True if the video already has detail data.

    Checks multiple detail-only fields (date, duration, maker) because some
    videos legitimately lack individual fields (e.g. no rating score).
    """
    row = conn.execute(
        "SELECT date, duration, maker FROM videos WHERE code=?", (code,)
    ).fetchone()
    if row is None:
        return False
    return bool(row["date"]) or bool(row["duration"]) or bool(row["maker"])


def get_videos_missing_magnets(conn, days=60, limit=20):
    rows = conn.execute("""
        SELECT code FROM videos
        WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)
        AND date IS NOT NULL AND date != ''
        AND date >= date('now', 'localtime', '-' || ? || ' days')
        ORDER BY date DESC
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
