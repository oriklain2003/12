import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.version import BUILD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
from app.routers.cubes import router as cubes_router
from app.routers.workflows import router as workflows_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)

    # DB pool warm-up
    from app.database import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("DB connection pool warmed")

    # Coverage baseline pre-warm (non-blocking background task)
    from app.signal.rule_based import start_coverage_baseline_build
    asyncio.create_task(start_coverage_baseline_build())
    log.info("Coverage baseline build started in background")

    yield


app = FastAPI(title="Project 12 — Flow", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cubes_router)
app.include_router(workflows_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api")
async def api_root() -> dict[str, str]:
    return {"message": "Project 12 API"}


@app.get("/api/version")
async def version() -> dict[str, int]:
    return {"build": BUILD}
