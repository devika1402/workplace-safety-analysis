"""Narrative-hash cache so re-runs skip already classified incidents.

Hashes the concatenated narratives (sha256) and stores validated classifications
in the raw llm_cache table keyed by (narrative_hash, prompt_version). A cache hit
means no model call, which makes re-runs idempotent and (for a paid API) free.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.settings import Settings
from enrichment.prompt import NARRATIVE_FIELDS
from enrichment.schemas import EventCategory, IncidentClassification, SeverityTier

logger = logging.getLogger(__name__)


def narrative_hash(narratives: Mapping[str, str | None]) -> str:
    """Return a stable sha256 hex digest of the concatenated narrative fields."""
    parts = [(narratives.get(field) or "") for field in NARRATIVE_FIELDS]
    joined = "␟".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _cache_identifier(engine: Engine, settings: Settings) -> str:
    """Return the quoted cache table name (schema-qualified except on SQLite)."""
    if engine.dialect.name == "sqlite":
        return f'"{settings.llm_cache_table}"'
    return f'"{settings.raw_schema}"."{settings.llm_cache_table}"'


def ensure_cache_table(engine: Engine, settings: Settings) -> None:
    """Create the cache table (and raw schema) if they do not yet exist."""
    identifier = _cache_identifier(engine, settings)
    with engine.begin() as connection:
        if engine.dialect.name != "sqlite":
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.raw_schema}"'))
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {identifier} (
                    narrative_hash text NOT NULL,
                    prompt_version text NOT NULL,
                    contributing_factor text NOT NULL,
                    severity_tier text NOT NULL,
                    event_category text NOT NULL,
                    recurrence_prevention text NOT NULL,
                    confidence double precision NOT NULL,
                    model_name text NOT NULL,
                    cached_at timestamp NOT NULL,
                    PRIMARY KEY (narrative_hash, prompt_version)
                )
                """
            )
        )


def get_cached(
    engine: Engine, settings: Settings, narrative_hash_value: str
) -> IncidentClassification | None:
    """Return the cached classification for a hash, or None on a miss."""
    identifier = _cache_identifier(engine, settings)
    with engine.begin() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT contributing_factor, severity_tier, event_category,
                       recurrence_prevention, confidence
                FROM {identifier}
                WHERE narrative_hash = :hash AND prompt_version = :version
                """
            ),
            {"hash": narrative_hash_value, "version": settings.prompt_version},
        ).fetchone()
    if row is None:
        return None
    return IncidentClassification(
        contributing_factor=row[0],
        severity_tier=SeverityTier(row[1]),
        event_category=EventCategory(row[2]),
        recurrence_prevention=row[3],
        confidence=row[4],
    )


def put_cached(
    engine: Engine,
    settings: Settings,
    narrative_hash_value: str,
    classification: IncidentClassification,
    model_name: str,
) -> None:
    """Insert a classification into the cache (no-op if already present)."""
    identifier = _cache_identifier(engine, settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                INSERT INTO {identifier} (
                    narrative_hash, prompt_version, contributing_factor,
                    severity_tier, event_category, recurrence_prevention,
                    confidence, model_name, cached_at
                ) VALUES (
                    :hash, :version, :contributing_factor, :severity_tier,
                    :event_category, :recurrence_prevention, :confidence,
                    :model_name, CURRENT_TIMESTAMP
                )
                ON CONFLICT (narrative_hash, prompt_version) DO NOTHING
                """
            ),
            {
                "hash": narrative_hash_value,
                "version": settings.prompt_version,
                "contributing_factor": classification.contributing_factor,
                "severity_tier": classification.severity_tier.value,
                "event_category": classification.event_category.value,
                "recurrence_prevention": classification.recurrence_prevention,
                "confidence": classification.confidence,
                "model_name": model_name,
            },
        )
