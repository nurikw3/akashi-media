"""Public + authenticated page routes for the composer shell.

Feature slices (S1 repackage, S2/S3 publish) attach their htmx endpoints to
this router. S0 ships the health check and the login-gated main page.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.entrypoints.web.auth import require_user


def register_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    router = APIRouter()

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "index.html", {"user": user})

    app.include_router(router)
