import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/favorites", dependencies=[Depends(require_auth)])

PAGE_SIZE = 20


@router.get("")
async def favorites_list(
    request: Request,
    q: str = Query(default=""),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
):
    valid_sorts = {"code", "title", "score", "date", "created_at"}
    if sort not in valid_sorts:
        sort = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        where_clauses = ["v.deleted=0"]
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(*) as c FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress,
                   1 as is_favorited
            FROM videos v
            JOIN favorites f ON v.code = f.video_code
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template_name = "favorites_content.html" if request.headers.get("HX-Request") else "favorites.html"

        return templates.TemplateResponse(request, template_name, {
            "videos": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "q": q,
            "sort": sort,
            "order": order,
        })
    finally:
        conn.close()
