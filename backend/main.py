from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api import router as api_router
from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.core.rate_limit import limiter
from backend.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)

    await init_redis()

    yield

    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
