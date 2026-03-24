"""initial

Revision ID: 9e61c7c6966b
Revises:
Create Date: 2026-03-23 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e61c7c6966b"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL не поддерживает CREATE TYPE IF NOT EXISTS,
    # поэтому используем DO-блок: создаём тип или молча игнорируем если уже есть.
    # Это гарантирует идемпотентность на любой БД — чистой или уже существующей.
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE audit_status AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS audit_requests (
            id          UUID                     NOT NULL PRIMARY KEY,
            channel_username VARCHAR(255)        NOT NULL,
            status      audit_status             NOT NULL,
            report      JSONB,
            error_message VARCHAR(1024),
            created_at  TIMESTAMPTZ              NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ              NOT NULL DEFAULT now()
        )
    """))

    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_requests_channel_username "
        "ON audit_requests (channel_username)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_requests_status "
        "ON audit_requests (status)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_requests_status"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_requests_channel_username"))
    op.execute(sa.text("DROP TABLE IF EXISTS audit_requests"))
    op.execute(sa.text("DROP TYPE IF EXISTS audit_status"))
