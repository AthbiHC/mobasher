from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routers import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Mobasher API", version="0.1.0")
    app.include_router(api_router)
    
    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(exc)})
    return app


app = create_app()


