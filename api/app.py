from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routers import products, subscribers
from config import PHOTOS_DIR
from database import dispose_engine, init_db


class MiniAppStaticFiles(StaticFiles):
    """Serves the built Mini App (webapp/dist).

    Telegram WebViews (especially Desktop) cache aggressively and ignore
    conventional revalidation, so index.html is never cached: a deploy is
    visible on the next open. Vite puts a content hash in every file name
    under assets/, so those can be cached for good.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# `npm run build` in webapp/ writes here; the build is committed, so the
# server needs no Node.
WEBAPP_DIR = PROJECT_ROOT / "webapp" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(seed=True)
    logger.info("API started.")
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("API stopped.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AKTAVIS.EU Mini App API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    if PHOTOS_DIR.exists():
        app.mount(
            "/photos",
            StaticFiles(directory=PHOTOS_DIR),
            name="photos",
        )
    else:
        logger.warning("Photos directory not found: %s", PHOTOS_DIR)

    app.include_router(products.router, prefix="/api")
    app.include_router(subscribers.router, prefix="/api")

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/webapp/")

    if WEBAPP_DIR.exists():
        app.mount(
            "/webapp",
            MiniAppStaticFiles(directory=WEBAPP_DIR, html=True),
            name="webapp",
        )
    else:
        logger.warning("Webapp directory not found: %s", WEBAPP_DIR)

    return app


app = create_app()
