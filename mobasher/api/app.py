from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .routers import router as api_router
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
import time


def create_app() -> FastAPI:
    app = FastAPI(title="Mobasher API", version="0.1.0")
    app.include_router(api_router)
    
    # Prometheus metrics
    REQUEST_COUNT = Counter(
        "mobasher_api_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "mobasher_api_request_duration_seconds",
        "Latency of HTTP requests in seconds",
        ["method", "path", "status"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        # Normalize path: collapse dynamic segments minimally (FastAPI routes may contain variables)
        path = request.url.path
        method = request.method
        status = str(response.status_code)
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path, status=status).observe(elapsed)
        return response

    @app.get("/metrics")
    async def metrics() -> Response:
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    
    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(exc)})
    return app


app = create_app()


