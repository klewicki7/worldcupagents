import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.rate_limit import limiter
from app.api.routers import auth as auth_router
from app.api.routers import me as me_router
from app.config import settings
from app.db.session import async_session_factory
from app.lib.errors import WCAError

logger = logging.getLogger(__name__)

app = FastAPI(title="worldcupagents", version="0.1.0")

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

_default_origins = [
    "https://worldcupagents.com",
    "https://www.worldcupagents.com",
]
if settings.environment != "production":
    _default_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(auth_router.router)
app.include_router(me_router.router)


@app.exception_handler(WCAError)
async def _wca_error_handler(_: Request, exc: WCAError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": "RATE_LIMITED",
            "message": "too many requests",
            "details": {"limit": str(exc.detail)},
        },
        headers={"Retry-After": "60"},
    )


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    db_ok = False
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        logger.exception("healthz DB ping failed")
    return {"status": "ok", "db": db_ok}
