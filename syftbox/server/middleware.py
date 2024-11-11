import time

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from syftbox.server.analytics import log_analytics_event


class LoguruMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"{request.method} {request.url.path}")
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.2f}s")

        return response


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        email = request.headers.get("email")
        if not email:
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        total_time = time.time() - start_time

        log_analytics_event(
            endpoint=request.url.path,
            email=email,
            duration=total_time,
            status=response.status_code,
        )

        return response
