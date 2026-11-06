import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

import backend.models  # noqa: F401
from backend.core.database import Base
from backend.tests.conftest import TEST_DATABASE_URL, make_alembic_config

pytestmark = pytest.mark.integration


def sync_url() -> str:
    return TEST_DATABASE_URL.replace("+asyncpg", "+psycopg2")


def test_migrations_apply_revert_and_match_models(migrated_db: None) -> None:
    config = make_alembic_config()
    engine = create_engine(sync_url())

    try:
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert "audit_requests" not in inspect(connection).get_table_names()

        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert "audit_requests" in inspect(connection).get_table_names()
            drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)

        assert drift == []
    finally:
        command.upgrade(config, "head")
        engine.dispose()
