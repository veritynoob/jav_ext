from fastapi import Request, HTTPException
from src.config import WEB_PASSWORD

SESSION_KEY = "authenticated"


async def require_auth(request: Request):
    if not request.session.get(SESSION_KEY):
        raise HTTPException(status_code=401)


def verify_login(request: Request, password: str) -> bool:
    if password == WEB_PASSWORD:
        request.session[SESSION_KEY] = True
        return True
    return False


def logout(request: Request):
    request.session.clear()
