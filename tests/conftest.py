import os
import sqlite3
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: tests that require captured live fixture HTML (skip by default)"
    )


def load_fixture(name):
    """Read a test fixture file from tests/fixtures/. Shared by all test modules."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def conn(db_path):
    from src.db import init_db
    conn = init_db(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
