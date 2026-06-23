"""Single shared login (Scope Cut: единый логин/пароль for the marketing team).

Session is a signed cookie via Starlette's SessionMiddleware. No user store,
no roles — just one credential pair compared in constant time.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, FastAPI, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

SESSION_USER_KEY = "user"


class RequiresLoginError(Exception):
    """Raised by the auth dependency when no session user is present."""


async def requires_login_redirect(request: Request, exc: RequiresLoginError) -> RedirectResponse:
    """Exception handler: send unauthenticated browsers to the login page."""
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


def require_user(request: Request) -> str:
    """FastAPI dependency. Returns the logged-in username or triggers a redirect."""
    user = request.session.get(SESSION_USER_KEY)
    if not user:
        raise RequiresLoginError()
    return user


def _credentials_valid(settings, username: str, password: str) -> bool:
    # Constant-time comparison on both fields to avoid leaking via timing.
    user_ok = hmac.compare_digest(username.encode("utf-8"), settings.username.encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), settings.password.encode("utf-8"))
    return user_ok and pass_ok


def register_auth_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    router = APIRouter()

    @router.get("/login")
    async def login_form(request: Request):
        if request.session.get(SESSION_USER_KEY):
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @router.post("/login")
    async def login_submit(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
    ):
        settings = request.app.state.container.settings
        limiter = request.app.state.login_rate_limiter
        client_key = request.client.host if request.client else "unknown"

        if limiter.is_blocked(client_key):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Слишком много попыток. Повторите позже."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if _credentials_valid(settings, username, password):
            limiter.reset(client_key)
            # Store the canonical configured username, never the raw form value.
            request.session[SESSION_USER_KEY] = settings.username
            return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

        limiter.register_failure(client_key)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Неверный логин или пароль"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    @router.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    app.include_router(router)
