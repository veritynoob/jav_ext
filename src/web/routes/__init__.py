from fastapi import FastAPI


def register_routers(app: FastAPI):
    from src.web.routes.dashboard import router as dashboard_router
    from src.web.routes.videos import router as videos_router
    from src.web.routes.actresses import router as actresses_router
    from src.web.routes.tasks import router as tasks_router

    app.include_router(dashboard_router)
    app.include_router(videos_router)
    app.include_router(actresses_router)
    app.include_router(tasks_router)

    _register_login(app)


def _register_login(app: FastAPI):
    from fastapi import Request, Form
    from fastapi.responses import RedirectResponse
    from src.web.app import templates
    from src.web.auth import verify_login

    @app.get("/login")
    async def login_page(request: Request):
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login")
    async def login_post(request: Request, password: str = Form(...)):
        if verify_login(request, password):
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid password"}, status_code=401)

    @app.get("/logout")
    async def logout_route(request: Request):
        from src.web.auth import logout
        logout(request)
        return RedirectResponse(url="/login", status_code=302)
