import sqlite3
from fastapi import APIRouter, Request, Query, Depends
from src.web.app import templates
from src.web.auth import require_auth
from src.db import get_db_path

router = APIRouter(prefix="/videos", dependencies=[Depends(require_auth)])

PAGE_SIZE = 20


@router.get("")
async def video_list(
    request: Request,
    q: str = Query(default=""),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    list_type: str = Query(default=""),
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
        where_clauses = []
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        if list_type:
            where_clauses.append("r.list_type = ?")
            params.append(list_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(DISTINCT v.code) as c FROM videos v
            LEFT JOIN rankings r ON v.code = r.video_code
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT DISTINCT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at, r.list_type, r.rank
            FROM videos v
            LEFT JOIN rankings r ON v.code = r.video_code
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template_name = "videos.html"
        if request.headers.get("HX-Request"):
            template_name = "videos_partial.html"

        return templates.TemplateResponse(template_name, {
            "request": request,
            "videos": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "q": q,
            "sort": sort,
            "order": order,
            "list_type": list_type,
        })
    finally:
        conn.close()
