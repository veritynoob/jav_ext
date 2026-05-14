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
