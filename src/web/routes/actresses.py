import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/actresses", dependencies=[Depends(require_auth)])


@router.get("")
async def actress_list(request: Request, q: str = Query(default="")):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if q:
            rows = conn.execute("""
                SELECT a.name, COUNT(*) as video_count
                FROM actresses a
                WHERE a.name LIKE ?
                GROUP BY a.name ORDER BY video_count DESC
            """, (f"%{q}%",)).fetchall()
        else:
            rows = conn.execute("""
                SELECT name, COUNT(*) as video_count
                FROM actresses GROUP BY name ORDER BY video_count DESC
                LIMIT 200
            """).fetchall()

        return templates.TemplateResponse("actresses.html", {
            "request": request, "actresses": rows, "q": q,
        })
    finally:
        conn.close()


@router.get("/{name}/videos")
async def actress_videos(request: Request, name: str):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        videos = conn.execute("""
            SELECT v.code, v.title, v.score, v.date, v.cover_url
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? ORDER BY v.date DESC
        """, (name,)).fetchall()

        return templates.TemplateResponse("actress_videos_partial.html", {
            "request": request, "name": name, "videos": videos,
        })
    finally:
        conn.close()
