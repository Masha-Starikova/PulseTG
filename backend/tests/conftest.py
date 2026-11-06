"""Общие фикстуры тестов.

Настройки окружения выставляются до импорта backend: модуль конфигурации создаёт
Settings при импорте. Переменные окружения приоритетнее .env, поэтому секреты
разработчика в тесты не попадают, а значения пустые.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import urlparse

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://pulsetg_test:pulsetg_test@127.0.0.1:55432/pulsetg_test",
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:56379/0")

if not urlparse(TEST_DATABASE_URL).path.endswith("_test"):
    raise RuntimeError("Тесты запускаются только на базе с суффиксом _test")

os.environ.update(
    {
        "DATABASE_URL": TEST_DATABASE_URL,
        "REDIS_URL": TEST_REDIS_URL,
        "CELERY_BROKER_URL": TEST_REDIS_URL.rsplit("/", 1)[0] + "/1",
        "CELERY_RESULT_BACKEND": TEST_REDIS_URL.rsplit("/", 1)[0] + "/2",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "test-model",
        "TELEGRAM_API_ID": "0",
        "TELEGRAM_API_HASH": "",
        "TELEGRAM_SESSION_NAME": "pulsetg_test",
        "DEBUG": "false",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

import backend.core.database as database  # noqa: E402
from backend.core.rate_limit import limiter  # noqa: E402
from backend.main import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_alembic_config() -> Config:
    # Config без пути к alembic.ini: иначе env.py перенастроит логирование всего процесса.
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    return config


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Схема создаётся настоящими миграциями, а не через metadata.create_all."""
    command.upgrade(make_alembic_config(), "head")


@pytest.fixture
async def engine(migrated_db: None) -> AsyncIterator[AsyncEngine]:
    # NullPool: соединение asyncpg привязано к event loop, а Celery-задача работает в своём.
    test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield test_engine
    async with test_engine.begin() as connection:
        await connection.execute(text("TRUNCATE audit_requests"))
    await test_engine.dispose()


@pytest.fixture
def session_factory(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> async_sessionmaker[AsyncSession]:
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    monkeypatch.setattr("backend.services.tasks.AsyncSessionLocal", factory)
    return factory


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Iterator[None]:
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
async def client(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[httpx.AsyncClient]:
    # ASGITransport не запускает lifespan, поэтому общий Redis-клиент здесь None.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
