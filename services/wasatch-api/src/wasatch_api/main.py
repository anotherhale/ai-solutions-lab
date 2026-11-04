"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wasatch_api import __version__
from wasatch_api.api.errors import register_exception_handlers
from wasatch_api.api.routes import (
    customer_service,
    customers,
    governance,
    health,
    work_orders,
)
from wasatch_api.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Wasatch Business Systems API",
        description=(
            "Read-only laboratory API for synthetic Wasatch Business Systems data. "
            "React and AI assistants are not part of this service."
        ),
        version=__version__,
    )
    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=["Accept"],
        )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(customers.router)
    app.include_router(work_orders.router)
    app.include_router(customer_service.router)
    app.include_router(governance.router)
    return app


app = create_app()
