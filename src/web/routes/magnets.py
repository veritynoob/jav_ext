import sqlite3
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/magnets", dependencies=[Depends(require_auth)])


@router.get("")
async def magnet_list(request: Request):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        missing = conn.execute("""
            SELECT code, title, date, created_at FROM videos
            WHERE code NOT IN (SELECT DISTINCT video_code FROM magnets)
            ORDER BY created_at DESC LIMIT 50
        """).fetchall()

        has_magnets = conn.execute("""
            SELECT v.code, v.title, COUNT(m.id) as magnet_count
            FROM videos v JOIN magnets m ON v.code = m.video_code
            GROUP BY v.code ORDER BY magnet_count DESC LIMIT 50
        """).fetchall()

        return templates.TemplateResponse("magnets.html", {
            "request": request, "missing": missing, "has_magnets": has_magnets,
        })
    finally:
        conn.close()
