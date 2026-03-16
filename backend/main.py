from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import router as api_router
from backend.core.config import settings
from backend.core.database import init_models
from backend.core.logging import setup_logging
from backend.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)

    # В local-среде можно автоматически создать таблицы.
    await init_models()
    await init_redis()

    yield

    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
