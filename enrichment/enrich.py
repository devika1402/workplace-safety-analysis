"""Read staged narratives, classify them, and write results to Postgres.

Reads incidents from the staging view, reuses cached classifications where
possible, calls the local LLM client for the rest, validates with Pydantic, and
upserts results into the raw llm_enrichment table keyed on incident_id. A single
failed row is logged and skipped; the run continues and reports counts.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pandas as pd
from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import Settings, get_settings
from enrichment.cache import (
    ensure_cache_table,
    get_cached,
    narrative_hash,
    put_cached,
)
from enrichment.client import build_client, classify_narrative
from enrichment.prompt import NARRATIVE_FIELDS, build_user_prompt
from enrichment.schemas import IncidentClassification

logger = logging.getLogger(__name__)

# The dbt staging model name is stable; the schema is configurable.
STAGING_CASE_DETAIL = "stg_osha__case_detail"

ClassifyFn = Callable[..., IncidentClassification | None]


def _clean(value: Any) -> str | None:
    """Normalize a raw cell to a stripped string or None (handles NaN/None)."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text_value = str(value).strip()
    return text_value or None


def _enrichment_identifier(engine: Engine, settings: Settings) -> str:
    if engine.dialect.name == "sqlite":
        return f'"{settings.llm_enrichment_table}"'
    return f'"{settings.raw_schema}"."{settings.llm_enrichment_table}"'


def _staging_identifier(engine: Engine, settings: Settings) -> str:
    if engine.dialect.name == "sqlite":
        return f'"{STAGING_CASE_DETAIL}"'
    return f'"{settings.staging_schema}"."{STAGING_CASE_DETAIL}"'


def ensure_enrichment_table(engine: Engine, settings: Settings) -> None:
    """Create the llm_enrichment table (and raw schema) if not present."""
    identifier = _enrichment_identifier(engine, settings)
    with engine.begin() as connection:
        if engine.dialect.name != "sqlite":
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.raw_schema}"'))
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {identifier} (
                    incident_id text PRIMARY KEY,
                    contributing_factor text NOT NULL,
                    severity_tier text NOT NULL,
                    event_category text NOT NULL,
                    recurrence_prevention text NOT NULL,
                    confidence double precision NOT NULL,
                    prompt_version text NOT NULL,
                    model_name text NOT NULL,
                    enriched_at timestamp NOT NULL
                )
                """
            )
        )


def _read_staged_incidents(
    engine: Engine, settings: Settings, limit: int | None
) -> list[dict[Any, Any]]:
    """Read incident_id, the six narratives, and sector from the staging view."""
    identifier = _staging_identifier(engine, settings)
    columns = ", ".join(["incident_id", *NARRATIVE_FIELDS, "industry_description"])
    query = f"SELECT {columns} FROM {identifier}"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    frame = pd.read_sql(query, engine)
    return frame.to_dict("records")


def _upsert_enrichment(
    engine: Engine,
    settings: Settings,
    incident_id: str,
    classification: IncidentClassification,
    model_name: str,
) -> None:
    """Insert or update one classification row keyed on incident_id."""
    identifier = _enrichment_identifier(engine, settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                INSERT INTO {identifier} (
                    incident_id, contributing_factor, severity_tier,
                    event_category, recurrence_prevention, confidence,
                    prompt_version, model_name, enriched_at
                ) VALUES (
                    :incident_id, :contributing_factor, :severity_tier,
                    :event_category, :recurrence_prevention, :confidence,
                    :prompt_version, :model_name, CURRENT_TIMESTAMP
                )
                ON CONFLICT (incident_id) DO UPDATE SET
                    contributing_factor = excluded.contributing_factor,
                    severity_tier = excluded.severity_tier,
                    event_category = excluded.event_category,
                    recurrence_prevention = excluded.recurrence_prevention,
                    confidence = excluded.confidence,
                    prompt_version = excluded.prompt_version,
                    model_name = excluded.model_name,
                    enriched_at = excluded.enriched_at
                """
            ),
            {
                "incident_id": incident_id,
                "contributing_factor": classification.contributing_factor,
                "severity_tier": classification.severity_tier.value,
                "event_category": classification.event_category.value,
                "recurrence_prevention": classification.recurrence_prevention,
                "confidence": classification.confidence,
                "prompt_version": settings.prompt_version,
                "model_name": model_name,
            },
        )


def run(
    settings: Settings | None = None,
    engine: Engine | None = None,
    client: OpenAI | None = None,
    classify: ClassifyFn | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """Enrich staged incidents and return a run summary.

    Args:
        settings: Configuration to use. Falls back to the process settings.
        engine: SQLAlchemy engine. Falls back to one built from the database URL.
        client: LLM client. Built lazily from settings if needed and not given.
        classify: Classification callable (injectable for tests). Defaults to the
            real client.classify_narrative.
        limit: Optional cap on the number of staged rows to process.

    Returns:
        A summary dict with rows_processed, rows_succeeded, rows_failed, and
        rows_from_cache.
    """
    settings = settings or get_settings()
    owns_engine = engine is None
    engine = engine or create_engine(settings.database_url)
    classify = classify or classify_narrative

    try:
        ensure_cache_table(engine, settings)
        ensure_enrichment_table(engine, settings)
        rows = _read_staged_incidents(engine, settings, limit)

        active_client = client
        processed = succeeded = failed = from_cache = 0

        for row in rows:
            processed += 1
            incident_id = str(row["incident_id"])
            narratives = {field: _clean(row.get(field)) for field in NARRATIVE_FIELDS}
            hash_value = narrative_hash(narratives)

            classification = get_cached(engine, settings, hash_value)
            if classification is not None:
                from_cache += 1
            else:
                if active_client is None:
                    active_client = build_client(settings)
                user_prompt = build_user_prompt(narratives, _clean(row.get("industry_description")))
                classification = classify(
                    active_client,
                    user_prompt,
                    incident_id=incident_id,
                    settings=settings,
                )
                if classification is None:
                    failed += 1
                    continue
                put_cached(engine, settings, hash_value, classification, settings.ollama_model)

            _upsert_enrichment(engine, settings, incident_id, classification, settings.ollama_model)
            succeeded += 1

        summary = {
            "rows_processed": processed,
            "rows_succeeded": succeeded,
            "rows_failed": failed,
            "rows_from_cache": from_cache,
        }
        logger.info("enrichment run summary: %s", summary)
        return summary
    finally:
        if owns_engine:
            engine.dispose()
