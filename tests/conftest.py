import os
import sqlite3
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    from db import init_db
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
