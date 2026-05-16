import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

app = FastAPI(title="worldcupagents", version="0.1.0")


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
