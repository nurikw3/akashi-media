"""uvicorn entry point: `python -m src.entrypoints.web.server` or via uvicorn.

Kept thin and excluded from coverage — it only loads env and starts the server.
"""

from __future__ import annotations

from src.config import create_app

app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("src.entrypoints.web.server:app", host="127.0.0.1", port=8001, reload=True)


if __name__ == "__main__":
    main()
