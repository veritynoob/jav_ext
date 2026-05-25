import pytest
from fastapi.testclient import TestClient
from src.web.app import create_app
from src.db import init_db, get_db_path, upsert_video, save_actresses, save_rankings, save_magnets


@pytest.fixture
def web_db_path(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_web.db")
    monkeypatch.setattr("src.db.get_db_path", lambda: db_path)
    monkeypatch.setattr("src.web.routes.dashboard.get_db_path", lambda: db_path)
    monkeypatch.setattr("src.web.routes.videos.get_db_path", lambda: db_path)
    monkeypatch.setattr("src.web.routes.actresses.get_db_path", lambda: db_path)
    monkeypatch.setattr("src.web.routes.favorites.get_db_path", lambda: db_path)
    return db_path


@pytest.fixture
def web_conn(web_db_path):
    conn = init_db(web_db_path)
    yield conn
    conn.close()


@pytest.fixture
def seed_data(web_conn):
    upsert_video(web_conn, {"code": "TEST-001", "title": "Test Video One", "cover_url": "http://example.com/1.jpg", "date": "2026-01-15", "duration": "120 min", "maker": "Studio A", "label": "Label X", "score": 8.5})
    upsert_video(web_conn, {"code": "TEST-002", "title": "Another Video", "cover_url": "http://example.com/2.jpg", "date": "2026-02-20", "duration": "90 min", "maker": "Studio B", "label": "Label Y", "score": 7.0})
    upsert_video(web_conn, {"code": "TEST-003", "title": "Third One Here", "cover_url": "http://example.com/3.jpg", "date": "2025-12-01", "duration": "150 min", "maker": "Studio A", "label": "Label Z", "score": 9.0})
    save_actresses(web_conn, "TEST-001", ["Alice", "Bob"])
    save_actresses(web_conn, "TEST-002", ["Alice"])
    save_actresses(web_conn, "TEST-003", ["Charlie"])
    save_rankings(web_conn, "most_wanted", [("TEST-001", "", 1), ("TEST-002", "", 5)])
    save_rankings(web_conn, "top_rated", [("TEST-001", "", 3)])
    save_magnets(web_conn, "TEST-001", ["magnet:?xt=urn:btih:aaa"])
    save_magnets(web_conn, "TEST-002", ["magnet:?xt=urn:btih:bbb", "magnet:?xt=urn:btih:ccc"])
    return web_conn


@pytest.fixture
def client(seed_data):
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"password": "admin"})
    return client


@pytest.fixture
def empty_client(web_conn):
    """A TestClient backed by an initialized but empty database (no seed data)."""
    app = create_app()
    client = TestClient(app)
    client.post("/login", data={"password": "admin"})
    return client


class TestAuth:
    def test_login_page_returns_200(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "login" in resp.text.lower()

    def test_login_success_redirects(self, client):
        resp = client.post("/login", data={"password": "admin"}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/"

    def test_login_wrong_password_returns_401(self, client):
        resp = client.post("/login", data={"password": "wrong"})
        assert resp.status_code == 401

    def test_logout_redirects_to_login(self, auth_client):
        resp = auth_client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/login"

    def test_protected_route_without_auth_redirects(self, client):
        resp = client.get("/videos", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["location"]


class TestDashboard:
    def test_dashboard_returns_200(self, auth_client):
        resp = auth_client.get("/")
        assert resp.status_code == 200

    def test_dashboard_shows_stats(self, auth_client):
        resp = auth_client.get("/")
        html = resp.text
        assert "3" in html  # total_videos
        assert "Alice" in html or "3" in html

    def test_dashboard_shows_recent(self, auth_client):
        resp = auth_client.get("/")
        assert "TEST-001" in resp.text or "TEST-002" in resp.text


class TestVideos:
    def test_video_list_returns_200(self, auth_client):
        resp = auth_client.get("/videos")
        assert resp.status_code == 200

    def test_video_list_shows_codes(self, auth_client):
        resp = auth_client.get("/videos")
        assert "TEST-001" in resp.text
        assert "TEST-002" in resp.text

    def test_video_list_search(self, auth_client):
        resp = auth_client.get("/videos?q=Another")
        assert "TEST-002" in resp.text
        assert "TEST-001" not in resp.text

    def test_video_list_search_case_insensitive(self, auth_client):
        resp = auth_client.get("/videos?q=another")
        assert "TEST-002" in resp.text

    def test_video_list_sort_and_order(self, auth_client):
        resp = auth_client.get("/videos?sort=score&order=asc")
        assert resp.status_code == 200

    def test_video_list_filter_list_type(self, auth_client):
        resp = auth_client.get("/videos?list_type=most_wanted")
        assert resp.status_code == 200
        assert "TEST-001" in resp.text

    def test_video_list_htmx_returns_partial(self, auth_client):
        resp = auth_client.get("/videos", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert 'video-grid' in resp.text.lower()

    def test_video_list_invalid_sort_falls_back(self, auth_client):
        resp = auth_client.get("/videos?sort=invalid")
        assert resp.status_code == 200

    def test_video_detail_returns_200(self, auth_client):
        resp = auth_client.get("/videos/TEST-001")
        assert resp.status_code == 200
        assert "Test Video One" in resp.text

    def test_video_detail_shows_actresses(self, auth_client):
        resp = auth_client.get("/videos/TEST-001")
        assert "Alice" in resp.text

    def test_video_detail_shows_magnets(self, auth_client):
        resp = auth_client.get("/videos/TEST-001")
        assert "magnet:" in resp.text

    def test_video_detail_shows_rankings(self, auth_client):
        resp = auth_client.get("/videos/TEST-001")
        assert "most_wanted" in resp.text or "#1" in resp.text

    def test_video_detail_not_found_returns_404(self, auth_client):
        resp = auth_client.get("/videos/NOEXIST")
        assert resp.status_code == 404

    def test_video_edit_form_returns_200(self, auth_client):
        resp = auth_client.get("/videos/TEST-001/edit")
        assert resp.status_code == 200
        assert "Test Video One" in resp.text

    def test_video_edit_form_not_found_returns_404(self, auth_client):
        resp = auth_client.get("/videos/NOEXIST/edit")
        assert resp.status_code == 404

    def test_video_edit_save_updates_title(self, auth_client):
        resp = auth_client.post("/videos/TEST-001/edit", data={
            "title": "Updated Title", "score": "9.5", "date": "2026-01-15",
            "duration": "120 min", "maker": "Studio A", "label": "Label X",
        }, follow_redirects=False)
        assert resp.status_code in (200, 302)

    def test_video_edit_save_empty_title_returns_422(self, auth_client):
        resp = auth_client.post("/videos/TEST-001/edit", data={
            "title": "", "score": "0", "date": "", "duration": "", "maker": "", "label": "",
        })
        assert resp.status_code == 422

    def test_video_edit_htmx_sets_trigger_header(self, auth_client):
        resp = auth_client.post("/videos/TEST-001/edit", data={
            "title": "HTMX Update", "score": "9.0", "date": "2026-01-15",
            "duration": "120 min", "maker": "Studio A", "label": "Label X",
        }, headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "HX-Trigger" in resp.headers
        assert "Saved successfully" in resp.headers["HX-Trigger"]

    def test_favorite_toggle(self, auth_client):
        resp = auth_client.post("/videos/TEST-001/favorite")
        assert resp.status_code == 200
        assert "★" in resp.text
        resp = auth_client.post("/videos/TEST-001/favorite")
        assert resp.status_code == 200
        assert "☆" in resp.text

    def test_favorite_appears_on_detail(self, auth_client):
        auth_client.post("/videos/TEST-001/favorite")
        resp = auth_client.get("/videos/TEST-001")
        assert "★" in resp.text

    def test_video_delete_redirects(self, auth_client):
        resp = auth_client.post("/videos/TEST-003/delete", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/videos"

    def test_deleted_video_not_in_list(self, auth_client):
        auth_client.post("/videos/TEST-003/delete")
        resp = auth_client.get("/videos")
        assert "TEST-003" not in resp.text

    def test_deleted_video_returns_404(self, auth_client):
        auth_client.post("/videos/TEST-002/delete")
        resp = auth_client.get("/videos/TEST-002")
        assert resp.status_code == 404

    def test_video_detail_shows_actress_jav_link(self, auth_client):
        from src.db import save_actresses, get_db_path
        import sqlite3
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        save_actresses(conn, "TEST-001", [("Alice", "alice123")])
        conn.close()
        resp = auth_client.get("/videos/TEST-001")
        assert "vl_star.php?s=alice123" in resp.text


class TestActresses:
    def test_actress_list_returns_200(self, auth_client):
        resp = auth_client.get("/actresses")
        assert resp.status_code == 200

    def test_actress_list_shows_names(self, auth_client):
        resp = auth_client.get("/actresses")
        assert "Alice" in resp.text

    def test_actress_list_search(self, auth_client):
        resp = auth_client.get("/actresses?q=Bob")
        assert "Bob" in resp.text
        assert "Charlie" not in resp.text

    def test_actress_videos_partial(self, auth_client):
        resp = auth_client.get("/actresses/Alice/videos")
        assert resp.status_code == 200
        assert "TEST-001" in resp.text
        assert "TEST-002" in resp.text


class TestTasks:
    def test_tasks_page_returns_200(self, auth_client):
        resp = auth_client.get("/tasks")
        assert resp.status_code == 200

    def test_task_status_returns_partial(self, auth_client):
        resp = auth_client.get("/tasks/status")
        assert resp.status_code == 200

    def test_trigger_scrape_starts_task(self, auth_client):
        resp = auth_client.post("/tasks/scrape", data={"list_type": "all"})
        assert resp.status_code == 200
        assert "HX-Trigger" in resp.headers

    def test_trigger_backfill_starts_task(self, auth_client):
        resp = auth_client.post("/tasks/backfill")
        assert resp.status_code == 200
        assert "HX-Trigger" in resp.headers


class TestFavorites:
    def test_favorites_page_returns_200(self, auth_client):
        resp = auth_client.get("/favorites")
        assert resp.status_code == 200

    def test_favorites_empty_state(self, auth_client):
        resp = auth_client.get("/favorites")
        assert "No favorites yet" in resp.text

    def test_favorites_shows_favorited(self, auth_client):
        auth_client.post("/videos/TEST-001/favorite")
        resp = auth_client.get("/favorites")
        assert "TEST-001" in resp.text
        assert "TEST-002" not in resp.text

    def test_favorites_htmx_returns_content(self, auth_client):
        auth_client.post("/videos/TEST-001/favorite")
        resp = auth_client.get("/favorites", headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "video-grid" in resp.text.lower()


class TestErrorPages:
    def test_404_page(self, auth_client):
        resp = auth_client.get("/nonexistent")
        assert resp.status_code == 404


class TestLayoutIntegration:
    """Integration tests for grid layout, empty states, sidebar and route changes."""

    def test_videos_page_returns_grid(self, auth_client):
        resp = auth_client.get("/videos")
        assert resp.status_code == 200
        assert "video-grid" in resp.text
        assert "video-card" in resp.text

    def test_actresses_page_shows_empty_state(self, empty_client):
        resp = empty_client.get("/actresses")
        assert resp.status_code == 200
        assert "No actresses found" in resp.text

    def test_magnets_route_removed(self, auth_client):
        resp = auth_client.get("/magnets")
        assert resp.status_code == 404

    def test_sidebar_no_dashboard_link(self, auth_client):
        resp = auth_client.get("/videos")
        assert "Dashboard" not in resp.text
        assert "Magnets" not in resp.text
