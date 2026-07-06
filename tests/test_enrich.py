"""Unit tests for enrichment.client and enrichment.enrich (LLM mocked).

No real model calls and no Ollama or API key are needed: the OpenAI client is
faked and classification is injected.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import Settings
from enrichment.client import classify_narrative
from enrichment.enrich import run
from enrichment.schemas import IncidentClassification

VALID_ARGS = (
    '{"contributing_factor": "wet floor", "severity_tier": "moderate", '
    '"event_category": "fall_slip_trip", "recurrence_prevention": '
    '"install anti-slip matting at the sink", "confidence": 0.7}'
)


def _settings() -> Settings:
    # Zero base delay so the retry path never actually sleeps in tests.
    return Settings(llm_retry_base_seconds=0.0, llm_max_retries=2)


def _fake_openai(behavior: Any) -> Any:
    completions = SimpleNamespace(create=behavior)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _response_with_args(arguments: str) -> Any:
    call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    message = SimpleNamespace(tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- classify_narrative: the three required cases ---------------------------


def test_classify_valid_response() -> None:
    fake = _fake_openai(lambda **kwargs: _response_with_args(VALID_ARGS))
    result = classify_narrative(fake, "prompt", incident_id="i1", settings=_settings())
    assert isinstance(result, IncidentClassification)
    assert result.event_category.value == "fall_slip_trip"


def test_classify_malformed_response_is_skipped() -> None:
    # confidence out of range -> Pydantic rejects -> row skipped (None).
    malformed = VALID_ARGS.replace("0.7", "5.0")
    fake = _fake_openai(lambda **kwargs: _response_with_args(malformed))
    result = classify_narrative(fake, "prompt", incident_id="i2", settings=_settings())
    assert result is None


def test_classify_api_error_is_skipped() -> None:
    def boom(**kwargs: Any) -> Any:
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))

    fake = _fake_openai(boom)
    result = classify_narrative(fake, "prompt", incident_id="i3", settings=_settings())
    assert result is None


def test_classify_coerces_unknown_event_category() -> None:
    # A weaker model may emit an out-of-enum category; coerce it to "other"
    # rather than dropping the row.
    unknown = VALID_ARGS.replace("fall_slip_trip", "cut_laceration")
    fake = _fake_openai(lambda **kwargs: _response_with_args(unknown))
    result = classify_narrative(fake, "prompt", incident_id="i4", settings=_settings())
    assert result is not None
    assert result.event_category.value == "other"


# --- enrich.run: continues past failures, writes, and uses the cache --------


def _make_db(rows: list[dict[str, str]]) -> Engine:
    engine = create_engine("sqlite://")
    columns = (
        "incident_id text, narrative_location text, narrative_description text, "
        "narrative_activity text, narrative_event text, narrative_injury text, "
        "narrative_source text, industry_description text"
    )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE stg_osha__case_detail ({columns})"))
        for row in rows:
            connection.execute(
                text(
                    "INSERT INTO stg_osha__case_detail "
                    "(incident_id, narrative_event, industry_description) "
                    "VALUES (:id, :event, :industry)"
                ),
                row,
            )
    return engine


def _classify_valid(*args: Any, **kwargs: Any) -> IncidentClassification:
    return IncidentClassification(
        contributing_factor="x",
        severity_tier="minor",
        event_category="other",
        recurrence_prevention="y",
        confidence=0.5,
    )


def test_run_writes_enrichment_rows() -> None:
    engine = _make_db(
        [
            {"id": "a", "event": "slipped", "industry": "Warehousing"},
            {"id": "b", "event": "cut hand", "industry": "Manufacturing"},
        ]
    )
    summary = run(settings=_settings(), engine=engine, client=object(), classify=_classify_valid)
    assert summary["rows_processed"] == 2
    assert summary["rows_succeeded"] == 2
    assert summary["rows_failed"] == 0
    count = pd.read_sql("select count(*) as c from llm_enrichment", engine).iloc[0]["c"]
    assert count == 2
    engine.dispose()


def test_run_skips_failed_rows_and_continues() -> None:
    engine = _make_db(
        [
            {"id": "a", "event": "slipped", "industry": "W"},
            {"id": "b", "event": "cut hand", "industry": "M"},
        ]
    )

    def classify(client: Any, user_prompt: str, *, incident_id: str, settings: Any) -> Any:
        return None if incident_id == "a" else _classify_valid()

    summary = run(settings=_settings(), engine=engine, client=object(), classify=classify)
    assert summary["rows_processed"] == 2
    assert summary["rows_succeeded"] == 1
    assert summary["rows_failed"] == 1
    written = pd.read_sql("select incident_id from llm_enrichment", engine)
    assert list(written["incident_id"]) == ["b"]
    engine.dispose()


def test_run_uses_cache_on_second_run() -> None:
    engine = _make_db([{"id": "a", "event": "slipped", "industry": "W"}])
    settings = _settings()
    run(settings=settings, engine=engine, client=object(), classify=_classify_valid)

    def must_not_call(*args: Any, **kwargs: Any) -> IncidentClassification:
        raise AssertionError("the model must not be called on a cache hit")

    summary = run(settings=settings, engine=engine, client=object(), classify=must_not_call)
    assert summary["rows_from_cache"] == 1
    assert summary["rows_succeeded"] == 1
    assert summary["rows_failed"] == 0
    engine.dispose()
