from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routers import products
from config import PHOTOS_DIR
from database import dispose_engine, init_db

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = PROJECT_ROOT / "webapp"


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

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/webapp/")

    if WEBAPP_DIR.exists():
        app.mount(
            "/webapp",
            StaticFiles(directory=WEBAPP_DIR, html=True),
            name="webapp",
        )
    else:
        logger.warning("Webapp directory not found: %s", WEBAPP_DIR)

    return app


app = create_app()
