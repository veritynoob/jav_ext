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
        from src.main import scrape_magnets
        processed, failed = scrape_magnets()
        _task_status[task_id] = {"status": "done", "message": f"Backfill complete: {processed} processed, {failed} failed", "finished_at": datetime.now().isoformat()}
    except Exception as e:
        _task_status[task_id] = {"status": "error", "message": str(e), "finished_at": datetime.now().isoformat()}


@router.get("")
async def tasks_page(request: Request):
    template_name = "tasks.html"
    if request.headers.get("HX-Request"):
        template_name = "tasks_partial.html"
    return templates.TemplateResponse(request, template_name, {
        "tasks": _task_status,
    })


@router.post("/scrape")
async def trigger_scrape(request: Request, list_type: str = "all"):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_scrape, args=(task_id, list_type), daemon=True)
    t.start()
    resp = templates.TemplateResponse(request, "task_status_partial.html", {"tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Scrape task started", "type": "success"}}'
    return resp


@router.post("/backfill")
async def trigger_backfill(request: Request):
    task_id = str(uuid.uuid4())[:8]
    t = threading.Thread(target=_run_backfill, args=(task_id,), daemon=True)
    t.start()
    resp = templates.TemplateResponse(request, "task_status_partial.html", {"tasks": _task_status})
    resp.headers["HX-Trigger"] = '{"toast": {"msg": "Backfill task started", "type": "success"}}'
    return resp


@router.get("/status")
async def task_status(request: Request):
    return templates.TemplateResponse(request, "task_status_partial.html", {
        "tasks": _task_status,
    })
