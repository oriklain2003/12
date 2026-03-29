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
from app.agents.router import router as agent_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = logging.getLogger(__name__)

    # DB pool warm-up (non-fatal — App Runner health checks must pass even if DB is slow)
    from app.database import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("DB connection pool warmed")
    except Exception as exc:
        log.warning("DB warm-up failed (will retry on first request): %s", exc)

    # Coverage baseline pre-warm (non-blocking background task)
    from app.signal.rule_based import start_coverage_baseline_build
    asyncio.create_task(start_coverage_baseline_build())
    log.info("Coverage baseline build started in background")

    # Agent infrastructure (Phase 18)
    from app.agents.client import init_client, close_client
    from app.agents.sessions import start_cleanup_task
    from app.agents.skills_loader import load_skill_files

    # Import tools to trigger decorator registration
    import app.agents.tools.catalog_tools  # noqa: F401

    load_skill_files()
    log.info("Agent skill files loaded")

    if settings.gemini_api_key:
        await init_client()
        log.info("Gemini client initialized")
    else:
        log.warning("GEMINI_API_KEY not set — agent endpoints will fail")

    cleanup_task = asyncio.create_task(start_cleanup_task())
    log.info("Agent session cleanup task started")

    yield

    # Agent cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    from app.agents.client import close_client
    await close_client()
    log.info("Agent infrastructure shut down")


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
app.include_router(agent_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api")
async def api_root() -> dict[str, str]:
    return {"message": "Project 12 API"}


@app.get("/api/version")
async def version() -> dict[str, int]:
    return {"build": BUILD}
