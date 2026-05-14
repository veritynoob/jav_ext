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
