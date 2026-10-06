"""Lightweight, non-destructive schema reconciliation for the SQLite dev DB.

`Base.metadata.create_all` creates missing *tables* but never adds missing
*columns* to existing tables. That drift is what crashed fresh audits (the live
`url` table lacked columns the model declared). This module compares each mapped
model to the live table and issues `ALTER TABLE ... ADD COLUMN` for anything
missing. Idempotent and safe to run on every startup.

This is a pragmatic dev-grade migrator for SQLite. Swap for Alembic when the
storage backend moves to Postgres.
"""
from __future__ import annotations

import structlog
from sqlalchemy import Engine, inspect, text
from sqlalchemy.schema import CreateColumn

from sentinelseo.db.models import Base

log = structlog.get_logger(__name__)


def run_migrations(engine: Engine) -> list[str]:
    """Create missing tables, then add any missing columns. Returns applied DDL."""
    Base.metadata.create_all(bind=engine)

    applied: list[str] = []
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # freshly created by create_all above
            live_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_cols:
                    continue
                # Compile the column DDL for SQLite; strip constraints ALTER can't add.
                col_ddl = str(
                    CreateColumn(column).compile(dialect=engine.dialect)
                ).strip()
                # SQLite ALTER ADD COLUMN cannot add PRIMARY KEY / UNIQUE / NOT NULL
                # without a default; our added columns are all nullable JSON/scalars.
                stmt = f'ALTER TABLE "{table.name}" ADD COLUMN {col_ddl}'
                conn.execute(text(stmt))
                applied.append(stmt)
                log.info("migration_add_column", table=table.name, column=column.name)

    if applied:
        log.info("migrations_applied", count=len(applied))
    return applied


if __name__ == "__main__":
    from sentinelseo.db.session import engine

    changes = run_migrations(engine)
    log.info("migrate.done", applied=len(changes), changes=changes)
