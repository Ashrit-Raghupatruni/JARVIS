"""
Middleware configuration for JARVIS API.

Provides CORS, global exception handling, and request logging.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI application."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "app://.",  # Electron custom protocol
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Skip logging for health checks and WebSocket upgrades
        if request.url.path in ("/", "/health", "/favicon.ico"):
            return await call_next(request)

        logger.debug(f"→ {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"← {request.method} {request.url.path} "
                f"[{response.status_code}] {duration:.1f}ms"
            )
            return response
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"✗ {request.method} {request.url.path} "
                f"[500] {duration:.1f}ms — {str(e)}"
            )
            raise

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if app.debug else "An unexpected error occurred.",
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "detail": f"Path {request.url.path} not found."},
        )
