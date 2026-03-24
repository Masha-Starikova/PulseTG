import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Импортируем Base и настройки приложения
from backend.core.database import Base
from backend.core.config import settings

# Импортируем все модели, чтобы они зарегистрировались в Base.metadata
# и autogenerate мог их обнаружить
import backend.models  # noqa: F401

# Alembic Config — доступ к значениям из alembic.ini
config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Метаданные всех наших моделей — нужны для autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline-режим: генерирует SQL-скрипты без подключения к БД.

    Полезно для создания SQL-дампа миграции без реального подключения.
    Запуск: alembic upgrade head --sql
    """
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online-режим: подключается к БД и применяет миграции через async engine."""
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,  # NullPool — каждый раз новое соединение, безопасно для миграций
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Точка входа для online-режима."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
