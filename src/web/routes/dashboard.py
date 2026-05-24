import sqlite3
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/")
async def dashboard(request: Request):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        total_videos = conn.execute("SELECT COUNT(*) as c FROM videos").fetchone()["c"]
        total_actresses = conn.execute("SELECT COUNT(DISTINCT name) as c FROM actresses").fetchone()["c"]
        today_new = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE date(created_at) = date('now','localtime')"
        ).fetchone()["c"]
        missing_magnets = conn.execute(
            "SELECT COUNT(*) as c FROM videos WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)"
        ).fetchone()["c"]

        recent = conn.execute(
            "SELECT code, title, score, date, created_at FROM videos ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        top_most_wanted = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='most_wanted' ORDER BY r.rank LIMIT 10"""
        ).fetchall()

        top_rated = conn.execute(
            """SELECT v.code, v.title, v.score, r.rank
               FROM rankings r JOIN videos v ON v.code = r.video_code
               WHERE r.list_type='top_rated' ORDER BY r.rank LIMIT 10"""
        ).fetchall()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": {
                "total_videos": total_videos,
                "total_actresses": total_actresses,
                "today_new": today_new,
                "missing_magnets": missing_magnets,
            },
            "recent": recent,
            "top_most_wanted": top_most_wanted,
            "top_rated": top_rated,
        })
    finally:
        conn.close()
