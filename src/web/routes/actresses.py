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

        template_name = "actresses.html"
        if request.headers.get("HX-Request"):
            template_name = "actresses_partial.html"

        return templates.TemplateResponse(request, template_name, {
            "actresses": rows, "q": q,
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
            SELECT v.code, v.title, v.score, v.date, v.cover_url,
                   (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0 ORDER BY v.date DESC
        """, (name,)).fetchall()

        return templates.TemplateResponse(request, "actress_videos_partial.html", {
            "name": name, "videos": videos,
        })
    finally:
        conn.close()


@router.get("/{name}")
async def actress_page(
    request: Request,
    name: str,
    sort: str = Query(default="date"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
):
    valid_sorts = {"code", "title", "score", "date", "created_at"}
    if sort not in valid_sorts:
        sort = "date"
    if order not in ("asc", "desc"):
        order = "desc"

    PAGE_SIZE = 20
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        count = conn.execute("""
            SELECT COUNT(*) as c
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
        """, (name,)).fetchone()["c"]
        total_pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        videos = conn.execute("""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker, v.created_at,
                   (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited
            FROM videos v JOIN actresses a ON v.code = a.video_code
            WHERE a.name = ? AND v.deleted=0
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """.format(sort=sort, order=order), (name, PAGE_SIZE, offset)).fetchall()

        template_name = "actress_videos_content.html" if request.headers.get("HX-Request") else "actress_videos.html"

        return templates.TemplateResponse(request, template_name, {
            "name": name,
            "videos": videos,
            "total": count,
            "page": page,
            "total_pages": total_pages,
            "sort": sort,
            "order": order,
        })
    finally:
        conn.close()
