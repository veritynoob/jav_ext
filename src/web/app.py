from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import WEB_SECRET_KEY

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def create_app() -> FastAPI:
    app = FastAPI(title="JAV Management Panel")

    app.add_middleware(SessionMiddleware, secret_key=WEB_SECRET_KEY)

    from src.web.routes import register_routers
    register_routers(app)

    @app.exception_handler(401)
    async def auth_exception_handler(request: Request, exc):
        return RedirectResponse(url="/login", status_code=302)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return templates.TemplateResponse(request, "404.html", status_code=404)

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        return templates.TemplateResponse(request, "500.html", status_code=500)

    return app


app = create_app()
