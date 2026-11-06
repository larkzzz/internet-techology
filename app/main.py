import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import DbSession
from app.logging_config import get_logger, setup_logging
from app.routers import comments, labels, projects, tasks, users

setup_logging(settings.log_level, settings.log_format)
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "TaskFlow API started (log_level=%s, log_format=%s)",
        settings.log_level,
        settings.log_format,
    )
    yield
    logger.info("TaskFlow API stopped")


app = FastAPI(title="TaskFlow API", version="1.0.0", lifespan=lifespan)

app.include_router(users.router, prefix="/v1/users", tags=["users"])
app.include_router(projects.router, prefix="/v1/projects", tags=["projects"])
app.include_router(labels.router, prefix="/v1/labels", tags=["labels"])
app.include_router(tasks.router, prefix="/v1/tasks", tags=["tasks"])
app.include_router(comments.router, prefix="/v1/comments", tags=["comments"])


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
    duration_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError) -> Response:
    fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
    logger.warning(
        "Validation error on %s %s: %s", request.method, request.url.path, ", ".join(fields)
    )
    return await request_validation_exception_handler(request, exc)


@app.get("/health", tags=["health"])
def health(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.critical("Health check failed: database is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    logger.debug("Health check passed")
    return {"status": "ok", "database": "up"}
