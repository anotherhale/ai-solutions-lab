"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wasatch_api import __version__
from wasatch_api.api.errors import register_exception_handlers
from wasatch_api.api.middleware import LaboratoryAccessMiddleware
from wasatch_api.api.routes import (
    customer_service,
    customers,
    documents,
    governance,
    health,
    work_orders,
    workflows,
)
from wasatch_api.config import get_settings, reject_unsafe_production_configuration
from wasatch_api.shared.logging import configure_logging
from wasatch_api.workforce.infrastructure.local_authenticator import (
    LABORATORY_ACTOR_HEADER,
)


def create_app() -> FastAPI:
    settings = get_settings()
    reject_unsafe_production_configuration(settings.app_env)
    configure_logging(settings.app_log_level)
    app = FastAPI(
        title="Wasatch Business Systems API",
        description=(
            "Laboratory API for synthetic Wasatch Business Systems data. "
            f"{LABORATORY_ACTOR_HEADER} is a local synthetic development "
            "identity simulation. Reads of customer, employee, and document "
            "data require that header. An active employee may draft a suggested "
            "reply. An approver may approve or reject a pending customer "
            "message, and may accept or reject a document extraction that "
            "is awaiting review. Neither customer-message command sends the "
            "message. The extraction decision does not post a payment or "
            "change an invoice. A dispatcher may open a follow-up visit from "
            "an approved customer message and then confirm or cancel it. The "
            "visit stays unscheduled until that decision. The command does "
            "not send the message, assign a technician, or post finance. "
            "Other writes are denied. "
            "The model provider defaults to a fake that does not call the "
            "network. Procedure-page embeddings, when filled, use that same "
            "fake port and are not a trusted model. Production configuration "
            "refuses to start. React is not part of this service."
        ),
        version=__version__,
    )
    app.add_middleware(LaboratoryAccessMiddleware, app_env=settings.app_env)
    origins = settings.cors_origin_list()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
            allow_headers=["Accept", LABORATORY_ACTOR_HEADER],
        )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(customers.router)
    app.include_router(work_orders.router)
    app.include_router(customer_service.router)
    app.include_router(governance.router)
    app.include_router(documents.router)
    app.include_router(workflows.router)
    return app


app = create_app()
