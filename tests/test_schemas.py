"""Unit tests for enrichment.schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from enrichment.schemas import EventCategory, IncidentClassification, SeverityTier


def test_event_category_values_match_contract() -> None:
    # These values are mapped against OIICS in mart_llm_eval and must not drift.
    assert {member.value for member in EventCategory} == {
        "struck_by_or_against",
        "fall_slip_trip",
        "overexertion_bodily_reaction",
        "exposure_harmful_substance",
        "contact_with_equipment",
        "transportation",
        "fire_explosion",
        "violence",
        "other",
    }


def test_severity_tier_values() -> None:
    assert [member.value for member in SeverityTier] == [
        "minor",
        "moderate",
        "serious",
        "severe",
    ]


def test_valid_classification() -> None:
    classification = IncidentClassification(
        contributing_factor="missing machine guard",
        severity_tier="serious",
        event_category="contact_with_equipment",
        recurrence_prevention="install a fixed guard on the press",
        confidence=0.8,
    )
    assert classification.severity_tier is SeverityTier.serious
    assert classification.event_category is EventCategory.contact_with_equipment


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        IncidentClassification(
            contributing_factor="x",
            severity_tier="minor",
            event_category="other",
            recurrence_prevention="y",
            confidence=1.5,
        )


def test_contributing_factor_max_length_enforced() -> None:
    with pytest.raises(ValidationError):
        IncidentClassification(
            contributing_factor="x" * 201,
            severity_tier="minor",
            event_category="other",
            recurrence_prevention="y",
            confidence=0.5,
        )


def test_invalid_event_category_rejected() -> None:
    with pytest.raises(ValidationError):
        IncidentClassification(
            contributing_factor="x",
            severity_tier="minor",
            event_category="not_a_real_category",
            recurrence_prevention="y",
            confidence=0.5,
        )
