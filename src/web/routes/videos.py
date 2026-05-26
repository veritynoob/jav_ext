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
        where_clauses = ["v.deleted=0"]
        params = []

        if q:
            where_clauses.append("(v.code LIKE ? OR v.title LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        if list_type:
            where_clauses.append("v.code IN (SELECT video_code FROM rankings WHERE list_type = ?)")
            params.append(list_type)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_sql = f"SELECT COUNT(*) as c FROM videos v {where_sql}"
        total = conn.execute(count_sql, params).fetchone()["c"]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        offset = (page - 1) * PAGE_SIZE

        data_sql = f"""
            SELECT v.code, v.title, v.cover_url, v.score, v.date, v.maker,
                   v.created_at,
                   (SELECT a.name FROM actresses a WHERE a.video_code = v.code ORDER BY a.name LIMIT 1) as first_actress,
                   (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited
            FROM videos v
            {where_sql}
            ORDER BY v.{sort} {order}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(data_sql, params + [PAGE_SIZE, offset]).fetchall()

        template_name = "videos_content.html" if request.headers.get("HX-Request") else "videos.html"

        return templates.TemplateResponse(request, template_name, {
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


@router.get("/{code}")
async def video_detail(request: Request, code: str):
    ref = request.headers.get("Referer", "")
    if ref and "/videos/" not in ref:
        request.session["prev_page"] = ref

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        video = conn.execute(
            "SELECT v.*, (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited "
            "FROM videos v WHERE v.code=? AND v.deleted=0", (code,)
        ).fetchone()
        if not video:
            return templates.TemplateResponse(request, "404.html", status_code=404)

        actresses = conn.execute(
            "SELECT name, actress_id FROM actresses WHERE video_code=? ORDER BY name", (code,)
        ).fetchall()

        magnets = conn.execute(
            "SELECT magnet, source, title, size, magnet_date, download_count, created_at "
            "FROM magnets WHERE video_code=? ORDER BY created_at DESC", (code,)
        ).fetchall()

        rankings = conn.execute(
            "SELECT list_type, rank FROM rankings WHERE video_code=?", (code,)
        ).fetchall()

        tmpl = "video_detail_content.html" if request.headers.get("HX-Request") else "video_detail.html"
        return templates.TemplateResponse(request, tmpl, {
            "video": video,
            "actresses": actresses,
            "magnets": magnets,
            "rankings": rankings,
            "is_favorited": bool(video["is_favorited"]),
        })
    finally:
        conn.close()


@router.get("/{code}/edit")
async def video_edit_form(request: Request, code: str):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
        if not video:
            return templates.TemplateResponse(request, "404.html", status_code=404)
        return templates.TemplateResponse(request, "video_edit.html", {"video": video, "error": None})
    finally:
        conn.close()


@router.post("/{code}/edit")
async def video_edit_save(request: Request, code: str):
    from fastapi.responses import RedirectResponse

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        body = await request.form()
        title = body.get("title", "").strip()
        if not title:
            video = conn.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone()
            return templates.TemplateResponse(request, "video_edit.html", {"video": video, "error": "Title is required"}, status_code=422)

        conn.execute("""
            UPDATE videos SET title=?, score=?, date=?, duration=?, maker=?, label=?, updated_at=datetime('now','localtime')
            WHERE code=?
        """, (
            title,
            float(body.get("score", 0) or 0),
            body.get("date", ""),
            body.get("duration", ""),
            body.get("maker", ""),
            body.get("label", ""),
            code,
        ))
        conn.commit()

        if request.headers.get("HX-Request"):
            video = conn.execute(
                "SELECT v.*, (SELECT COUNT(*) FROM favorites f WHERE f.video_code = v.code) as is_favorited "
                "FROM videos v WHERE v.code=? AND v.deleted=0", (code,)
            ).fetchone()
            actresses = conn.execute(
                "SELECT name, actress_id FROM actresses WHERE video_code=? ORDER BY name", (code,)
            ).fetchall()
            magnets = conn.execute(
                "SELECT magnet, source, title, size, magnet_date, download_count, created_at "
                "FROM magnets WHERE video_code=?", (code,)
            ).fetchall()
            rankings = conn.execute("SELECT list_type, rank FROM rankings WHERE video_code=?", (code,)).fetchall()
            resp = templates.TemplateResponse(request, "video_detail_content.html", {
                "video": video, "actresses": actresses, "magnets": magnets, "rankings": rankings,
                "is_favorited": bool(video["is_favorited"]),
            })
            resp.headers["HX-Trigger"] = '{"toast": {"msg": "Saved successfully", "type": "success"}}'
            return resp

        return RedirectResponse(url=f"/videos/{code}", status_code=302)
    finally:
        conn.close()


@router.post("/{code}/favorite")
async def video_favorite_toggle(request: Request, code: str):
    from src.db import toggle_favorite

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        is_favorited = toggle_favorite(conn, code)
        return templates.TemplateResponse(request, "favorite_btn.html", {
            "code": code,
            "is_favorited": is_favorited,
        })
    finally:
        conn.close()


@router.post("/{code}/delete")
async def video_delete(request: Request, code: str):
    from fastapi.responses import RedirectResponse
    from src.db import soft_delete_video

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        soft_delete_video(conn, code)
        if request.headers.get("HX-Request"):
            from fastapi.responses import Response
            prev = request.session.get("prev_page", "/videos")
            return Response(status_code=200, headers={"HX-Redirect": prev})
        return RedirectResponse(url="/videos", status_code=302)
    finally:
        conn.close()
