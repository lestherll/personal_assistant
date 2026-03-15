from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.schemas import ErrorResponse
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    AuthError,
    ForbiddenError,
    NotFoundError,
    ServiceValidationError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        body = ErrorResponse(error="not_found", detail=str(exc))
        return JSONResponse(status_code=404, content=body.model_dump())

    @app.exception_handler(AlreadyExistsError)
    async def handle_already_exists(request: Request, exc: AlreadyExistsError) -> JSONResponse:
        body = ErrorResponse(error="already_exists", detail=str(exc))
        return JSONResponse(status_code=409, content=body.model_dump())

    @app.exception_handler(ServiceValidationError)
    async def handle_validation_error(
        request: Request, exc: ServiceValidationError
    ) -> JSONResponse:
        body = ErrorResponse(error="validation_error", detail=str(exc))
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(AuthError)
    async def handle_auth_error(request: Request, exc: AuthError) -> JSONResponse:
        body = ErrorResponse(error="not_authenticated", detail=str(exc))
        return JSONResponse(
            status_code=401,
            content=body.model_dump(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ForbiddenError)
    async def handle_forbidden(request: Request, exc: ForbiddenError) -> JSONResponse:
        body = ErrorResponse(error="forbidden", detail=str(exc))
        return JSONResponse(status_code=403, content=body.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception for %s %s", request.method, request.url)
        body = ErrorResponse(error="internal_server_error")
        return JSONResponse(status_code=500, content=body.model_dump())
