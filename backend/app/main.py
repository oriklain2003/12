import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
from app.routers.cubes import router as cubes_router
from app.routers.workflows import router as workflows_router

app = FastAPI(
    title="Project 12 — Flow",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cubes_router)
app.include_router(workflows_router)


@app.on_event("startup")
async def warm_db_pool():
    """Pre-warm the DB connection pool so first workflow doesn't pay cold-start penalty."""
    from app.database import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logging.getLogger(__name__).info("DB connection pool warmed")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api")
async def api_root() -> dict[str, str]:
    return {"message": "Project 12 API"}
