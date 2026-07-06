"""Pydantic models for LLM enrichment input and output.

Defines the structured classification the model must return for each incident
narrative. The EventCategory values are deliberately aligned with OIICS event
groupings so the dbt evaluation model (mart_llm_eval) can compare them fairly.
Do not rename these values without updating that mapping.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SeverityTier(str, Enum):
    """Coarse severity of the incident, inferred from the narrative."""

    minor = "minor"
    moderate = "moderate"
    serious = "serious"
    severe = "severe"


class EventCategory(str, Enum):
    """Coarse event category, designed to map onto OIICS event codes."""

    struck_by_or_against = "struck_by_or_against"
    fall_slip_trip = "fall_slip_trip"
    overexertion_bodily_reaction = "overexertion_bodily_reaction"
    exposure_harmful_substance = "exposure_harmful_substance"
    contact_with_equipment = "contact_with_equipment"
    transportation = "transportation"
    fire_explosion = "fire_explosion"
    violence = "violence"
    other = "other"


class IncidentClassification(BaseModel):
    """Structured classification of a single OSHA incident narrative."""

    contributing_factor: str = Field(
        ...,
        max_length=200,
        description="The primary contributing factor in one short phrase.",
    )
    severity_tier: SeverityTier
    event_category: EventCategory = Field(
        ...,
        description=(
            "Coarse event category, designed to map onto OIICS event codes for evaluation."
        ),
    )
    recurrence_prevention: str = Field(
        ...,
        max_length=300,
        description="One concrete, plausible action that could prevent recurrence.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model's self-reported confidence in the classification.",
    )
