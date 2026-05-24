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
