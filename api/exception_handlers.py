from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.schemas import ErrorResponse
from personal_assistant.services.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    ServiceValidationError,
)


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
