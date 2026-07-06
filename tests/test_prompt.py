"""Unit tests for enrichment.prompt."""

from __future__ import annotations

from enrichment.prompt import (
    NARRATIVE_FIELDS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)


def test_prompt_version_starts_at_v1() -> None:
    assert PROMPT_VERSION == "v1"


def test_system_prompt_instructs_abstention_and_concrete_action() -> None:
    text = SYSTEM_PROMPT.lower()
    # Abstain with "other" + low confidence when sparse.
    assert "other" in text
    assert "confidence" in text
    # Concrete operational action, not a platitude.
    assert "concrete" in text
    assert "be more careful" in text


def test_build_user_prompt_includes_narratives_and_sector() -> None:
    narratives = {field: f"text-{field}" for field in NARRATIVE_FIELDS}
    prompt = build_user_prompt(narratives, "Warehousing")
    assert "Warehousing" in prompt
    for field in NARRATIVE_FIELDS:
        assert f"text-{field}" in prompt


def test_build_user_prompt_handles_missing_values() -> None:
    narratives = {field: None for field in NARRATIVE_FIELDS}
    prompt = build_user_prompt(narratives, None)
    assert "(not provided)" in prompt
    assert "unknown" in prompt
