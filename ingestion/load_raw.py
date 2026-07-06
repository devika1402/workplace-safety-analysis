"""Load the sampled OSHA Case Detail CSV into the Postgres raw schema.

Raw means raw: column names are lowercased and snake_cased, but values are
otherwise preserved. The load is idempotent (the table is replaced on each run).
The sampled data is small, so pandas is appropriate here; a production load at
full scale would stream or chunk, which is noted here for the reader.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Collapses any run of non-alphanumeric characters to a single underscore.
_NON_SNAKE = re.compile(r"[^0-9a-z]+")


def snake_case_columns(columns: list[str]) -> list[str]:
    """Lowercase and snake_case a list of column names.

    Non-alphanumeric runs collapse to single underscores; leading and trailing
    underscores are stripped.

    Args:
        columns: Original column names.

    Returns:
        Normalized column names.

    Raises:
        ValueError: If a name normalizes to an empty string.
    """
    normalized: list[str] = []
    for column in columns:
        cleaned = _NON_SNAKE.sub("_", column.strip().lower()).strip("_")
        if not cleaned:
            raise ValueError(f"Column name {column!r} normalizes to an empty string.")
        normalized.append(cleaned)
    return normalized


def load_raw(
    sampled_path: Path | None = None,
    settings: Settings | None = None,
    engine: Engine | None = None,
) -> int:
    """Load the sampled CSV into the raw case-detail table and return the row count.

    Args:
        sampled_path: Path to the sampled CSV. Falls back to the configured path.
        settings: Configuration to use. Falls back to the process settings.
        engine: SQLAlchemy engine. Falls back to one built from the database URL.

    Returns:
        The number of rows written.

    Raises:
        FileNotFoundError: If the sampled CSV does not exist.
    """
    settings = settings or get_settings()
    sampled_path = sampled_path or settings.sampled_csv_path
    if not sampled_path.exists():
        raise FileNotFoundError(
            f"Sampled CSV not found at {sampled_path}. Run the sample step first."
        )

    owns_engine = engine is None
    engine = engine or create_engine(settings.database_url)

    try:
        # Read every column as text so the landed types are stable regardless of
        # which rows the sample drew (pandas would otherwise infer an all-null
        # column as float, and strip leading zeros from zips). Raw means raw; the
        # dbt staging layer owns all casting.
        frame = pd.read_csv(sampled_path, dtype=str, low_memory=False)
        frame.columns = pd.Index(snake_case_columns([str(c) for c in frame.columns]))

        # SQLite (used in tests) has no schemas and no dependent objects.
        dialect = engine.dialect.name
        schema: str | None = None if dialect == "sqlite" else settings.raw_schema
        table = settings.case_detail_table

        if schema is None:
            frame.to_sql(table, con=engine, if_exists="replace", index=False)
        else:
            # Postgres: TRUNCATE then append instead of DROP and recreate, so the
            # dbt staging views that depend on this table survive a reload. A DROP
            # (what if_exists="replace" does) fails with DependentObjectsStillExist
            # once staging is built.
            relation = f"{schema}.{table}"
            with engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
                table_exists = (
                    connection.execute(
                        text("select to_regclass(:relation)"), {"relation": relation}
                    ).scalar()
                    is not None
                )
                if table_exists:
                    connection.execute(text(f'TRUNCATE TABLE "{schema}"."{table}"'))
            frame.to_sql(table, con=engine, schema=schema, if_exists="append", index=False)

        logger.info("Loaded %d rows into %s.%s", len(frame), schema or "main", table)
        return len(frame)
    finally:
        if owns_engine:
            engine.dispose()
