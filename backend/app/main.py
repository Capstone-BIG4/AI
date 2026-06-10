from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import api_router
from backend.app.core.paths import ASSETS, DOCS, FRONTEND, RUNTIME
from backend.app.core.settings import settings


def create_app() -> FastAPI:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title=settings.app_name, version=settings.version)
    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    app.mount("/styles", StaticFiles(directory=FRONTEND / "styles"), name="styles")
    app.mount("/src", StaticFiles(directory=FRONTEND / "src"), name="src")
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")
    app.mount("/docs", StaticFiles(directory=DOCS), name="docs")
    app.mount("/runtime", StaticFiles(directory=RUNTIME), name="runtime")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    return app


app = create_app()
