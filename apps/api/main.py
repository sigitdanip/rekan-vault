import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import settings
from apps.api.routers.direct_write import router as direct_write_router
from apps.api.routers.memory_review import router as memory_review_router
from apps.api.routers.search import router as search_router
from apps.api.routers.sources import router as sources_router
from rekanvault.contracts.errors import ErrorCode, ErrorDetail, ErrorEnvelope, RekanVaultError

START_TIME = time.time()

app = FastAPI(
    title="RekanVault API",
    version=settings.RV_RELEASE_VERSION,
    description="RekanVault Knowledge Base & RAG Engine API",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

allowed_origins = [orig.strip() for orig in settings.RV_ALLOWED_ORIGINS.split(",") if orig.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RekanVaultError)
async def rekanvault_error_handler(request: Request, exc: RekanVaultError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:16]}")
    envelope = exc.to_envelope(request_id)
    status_code = 500
    if exc.code == ErrorCode.NOT_FOUND:
        status_code = 404
    elif exc.code == ErrorCode.UNAUTHORIZED:
        status_code = 401
    elif exc.code == ErrorCode.FORBIDDEN:
        status_code = 403
    elif exc.code == ErrorCode.VALIDATION_ERROR:
        status_code = 422
    elif exc.code == ErrorCode.CONFLICT:
        status_code = 409
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:16]}")
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="Internal server error",
            details={"error_type": type(exc).__name__},
        ),
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": settings.RV_RELEASE_VERSION,
        "component": "rekanvault-api",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "environment": settings.RV_ENV,
    }


@app.get("/version", tags=["System"])
async def version_info() -> dict[str, Any]:
    return {
        "version": settings.RV_RELEASE_VERSION,
        "component_instance": settings.RV_COMPONENT_INSTANCE,
        "environment": settings.RV_ENV,
        "api_base_url": settings.RV_API_BASE_URL,
    }


app.include_router(sources_router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(search_router, prefix="/api/v1", tags=["Search"])
app.include_router(memory_review_router, prefix="/api/v1/memories", tags=["Memory"])
app.include_router(direct_write_router, prefix="/api/v1/memories", tags=["Memory"])


def export_openapi_schema(output_path: Path) -> None:
    schema = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(schema, indent=2))
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host=settings.RV_API_HOST, port=settings.RV_API_PORT, reload=True)
