"""FastAPI application factory.

Receives a fully built Container from the composition root (src/config.py) and
assembles the HTTP surface around it. Makes NO binding decisions itself — that
would violate the "wiring only in config.py" rule.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.config import Container
from src.entrypoints.web.auth import RequiresLoginError, register_auth_routes, requires_login_redirect
from src.entrypoints.web.routes import register_routes
from src.entrypoints.web.security import LoginRateLimiter, SecurityHeadersMiddleware

_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

_SESSION_MAX_AGE = 8 * 60 * 60  # 8 hours — internal shared credential


def build_web_app(container: Container) -> FastAPI:
    # /docs and /redoc disabled: this is an internal gateway behind a shared login.
    app = FastAPI(title="AkashiMedia", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.container = container
    app.state.login_rate_limiter = LoginRateLimiter()

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.state.templates = templates

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=container.settings.secret_key,
        same_site="strict",  # blocks cross-site cookie attach → CSRF mitigation for Phase 1
        https_only=container.settings.https_only,
        max_age=_SESSION_MAX_AGE,
    )
    app.add_exception_handler(RequiresLoginError, requires_login_redirect)

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    register_auth_routes(app, templates)
    register_routes(app, templates)
    return app
