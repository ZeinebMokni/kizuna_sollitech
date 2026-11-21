"""Domain errors and RFC 9457 problem+json handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

logger = logging.getLogger("qatra.errors")


class DomainError(Exception):
    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str, *, errors: list[dict] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.errors = errors


class NotFound(DomainError):
    status_code = 404
    title = "Not found"


class Forbidden(DomainError):
    status_code = 403
    title = "Forbidden"


class Unauthorized(DomainError):
    status_code = 401
    title = "Unauthorized"


class Conflict(DomainError):
    status_code = 409
    title = "Conflict"


class Unprocessable(DomainError):
    status_code = 422
    title = "Validation failed"


class TooManyRequests(DomainError):
    status_code = 429
    title = "Too many requests"


def problem(status: int, title: str, detail: str, errors: list | None = None) -> JSONResponse:
    body: dict = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return problem(exc.status_code, exc.title, exc.detail, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return problem(422, "Validation failed", "Request validation failed", errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, "HTTP error", str(exc.detail))
