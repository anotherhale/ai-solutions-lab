"""Consistent HTTP error envelopes."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from wasatch_api.shared.errors import (
    AuthorizationDenied,
    InvalidParameterError,
    NotFoundError,
    UnauthenticatedError,
)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_body("not_found", str(exc)))

    @app.exception_handler(InvalidParameterError)
    async def invalid_parameter(
        _request: Request, exc: InvalidParameterError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422, content=error_body("invalid_parameter", str(exc))
        )

    @app.exception_handler(UnauthenticatedError)
    async def unauthenticated(
        _request: Request, exc: UnauthenticatedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401, content=error_body("unauthenticated", str(exc))
        )

    @app.exception_handler(AuthorizationDenied)
    async def forbidden(_request: Request, exc: AuthorizationDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content=error_body("forbidden", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def request_validation(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("invalid_parameter", exc.errors()[0]["msg"]),
        )
