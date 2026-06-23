"""Public + authenticated page routes for the composer shell.

Feature slices (S1 repackage, S2/S3 publish) attach their htmx endpoints to
this router. S0 ships the health check and the login-gated main page.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.application.commands.repackage_for_linkedin import RepackageForLinkedInCommand
from src.domain.errors import ContentAdaptationError
from src.entrypoints.web.auth import require_user


def register_routes(app: FastAPI, templates: Jinja2Templates) -> None:
    router = APIRouter()

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "index.html", {"user": user})

    # Sync def: the LLM call is blocking I/O, so Starlette runs it in a
    # threadpool instead of stalling the event loop.
    @router.post("/repackage/linkedin", response_class=HTMLResponse)
    def repackage_linkedin(
        request: Request,
        source_text: str = Form(..., max_length=20_000),  # coarse DoS guard; command caps further
        user: str = Depends(require_user),
    ):
        command = RepackageForLinkedInCommand(request.app.state.container.content_adapter)
        try:
            adapted = command.execute(source_text)
        except ContentAdaptationError:
            return templates.TemplateResponse(
                request,
                "partials/linkedin_adapted.html",
                {"adapted_text": None, "error": "Не удалось адаптировать текст. Попробуйте ещё раз."},
            )
        return templates.TemplateResponse(
            request,
            "partials/linkedin_adapted.html",
            {"adapted_text": adapted, "error": None},
        )

    app.include_router(router)
