"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings, get_settings
from api.db.session import create_all, init_engine
from api.jobs.scheduler import build_scheduler
from api.routes import auth as auth_routes
from api.routes import health as health_routes
from api.routes import tasks as task_routes
from api.telemetry.otel import configure_telemetry


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not app.state.settings.scheduler_enabled:
        yield
        return
    scheduler = build_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app(settings: Settings | None = None, *, create_tables: bool = True) -> FastAPI:
    settings = settings or get_settings()
    init_engine(settings)
    if create_tables:
        create_all()

    app = FastAPI(
        title="rest-api-template",
        version="0.1.0",
        description="Production FastAPI scaffold with JWT+refresh auth, background jobs, OpenTelemetry.",
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(task_routes.router)

    configure_telemetry(app, settings)
    return app
