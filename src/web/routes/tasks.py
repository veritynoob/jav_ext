import threading
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from src.web.app import templates
from src.web.auth import require_auth

router = APIRouter(prefix="/tasks", dependencies=[Depends(require_auth)])

_task_status: dict[str, dict] = {}


def _run_scrape(task_id: str, list_type: str):
    _task_status[task_id] = {"status": "running", "message": f"Scraping {list_type}...", "started_at": datetime.now().isoformat()}
    try:
        from src.main import main as scrape_main
        scrape_main()
        _task_status[task_id] = {"status": "done", "message": "Scrape completed successfully", "finished_at": datetime.now().isoformat()}
    except Exception as e:
        _task_status[task_id] = {"status": "error", "message": str(e), "finished_at": datetime.now().isoformat()}


def _run_backfill(task_id: str):
    _task_status[task_id] = {"status": "running", "message": "Backfilling magnets...", "started_at": datetime.now().isoformat()}
    try:
        from src.config import MAGNET_BACKFILL_DAYS, MAX_BACKFILL_COUNT, SEARCH_BASE_URL, PROXY
        from src.db import init_db, get_videos_missing_magnets, update_video_search_url, save_magnets
        from src.scraper import parse_search_page
        from src.page_utils import load_with_cf_bypass
        import random
        import time

        conn = init_db()
        try:
            codes = get_videos_missing_magnets(conn, days=MAGNET_BACKFILL_DAYS, limit=MAX_BACKFILL_COUNT)
            for code in codes:
                _task_status[task_id]["message"] = f"Searching {code}..."
                search_url = f"{SEARCH_BASE_URL}/search/{code}"
                html = load_with_cf_bypass(search_url, proxy=PROXY, wait=random.uniform(3, 5), timeout=30, headless=True)
                if html:
                    _, magnets = parse_search_page(html, search_url)
                    if search_url:
                        update_video_search_url(conn, code, search_url)
                    if magnets:
                        save_magnets(conn, code, magnets)
                time.sleep(random.uniform(3, 5))
            _task_status[task_id] = {"status": "done", "message": f"Backfill complete: {len(codes)} videos processed", "finished_at": datetime.now().isoformat()}
        finally:
            conn.close()
    except Exception as e:
        _task_status[task_id] = {"status": "error", "message": str(e), "finished_at": datetime.now().isoformat()}


@router.get("")
async def tasks_page(request: Request):
    return templates.TemplateResponse("tasks.html", {
        "request": request, "tasks": _task_status,
    })


@router.post("/scrape")
async def trigger_scrape(request: Request, list_type: str = "all"):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_scrape, args=(task_id, list_type), daemon=True)
    t.start()
    resp = templates.TemplateResponse("tasks.html", {"request": request, "tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Scrape task started", "type": "success"}}'
    return resp


@router.post("/backfill")
async def trigger_backfill(request: Request):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_backfill, args=(task_id,), daemon=True)
    t.start()
    resp = templates.TemplateResponse("tasks.html", {"request": request, "tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Backfill task started", "type": "success"}}'
    return resp


@router.get("/status")
async def task_status(request: Request):
    return templates.TemplateResponse("task_status_partial.html", {
        "request": request, "tasks": _task_status,
    })
