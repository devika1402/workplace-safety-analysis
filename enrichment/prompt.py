"""Versioned prompt and prompt-building helpers for incident classification.

The prompt instructs the model to classify strictly from the narrative text, to
abstain (event_category 'other', low confidence) when the text is too sparse,
and to make recurrence_prevention a concrete operational action. PROMPT_VERSION
is stored with every enrichment row so outputs are traceable to the prompt that
produced them.
"""

from __future__ import annotations

from collections.abc import Mapping

PROMPT_VERSION = "v1"

# Staging narrative columns, in the order they are concatenated for hashing and
# rendered in the prompt block.
NARRATIVE_FIELDS: tuple[str, ...] = (
    "narrative_location",
    "narrative_description",
    "narrative_activity",
    "narrative_event",
    "narrative_injury",
    "narrative_source",
)

_NARRATIVE_LABELS: dict[str, str] = {
    "narrative_location": "Where it happened",
    "narrative_description": "Incident description",
    "narrative_activity": "What the employee was doing",
    "narrative_event": "What happened",
    "narrative_injury": "Injury or illness",
    "narrative_source": "Object or substance involved",
}

SYSTEM_PROMPT = (
    "You are an occupational safety analyst classifying workplace incident "
    "reports from OSHA narratives.\n\n"
    "Rules:\n"
    "- Base every field strictly on the narrative text provided. Do not invent "
    "details that are not present.\n"
    "- If the narrative is too sparse to classify the event, set event_category "
    'to "other" and report a low confidence (for example 0.2) rather than '
    "guessing. Honest abstention is preferred over a confident guess.\n"
    "- contributing_factor is one short phrase naming the primary cause.\n"
    "- recurrence_prevention must be one concrete, operational action (for "
    'example "install a machine guard on the press" or "add anti-slip matting '
    'at the sink"), never a platitude such as "be more careful" or "follow '
    'procedures".\n'
    "- severity_tier reflects how serious the outcome appears from the text.\n"
    "- Return your answer only by calling the provided classification tool."
)


def build_user_prompt(narratives: Mapping[str, str | None], sector: str | None) -> str:
    """Build the user prompt for one incident from its narratives and sector.

    Args:
        narratives: Mapping of narrative field name to text (any may be None).
        sector: Industry sector or description for context (may be None).

    Returns:
        A structured prompt string listing the industry and each narrative
        field, ready to send as the user message.
    """
    lines = [
        f"Industry: {sector or 'unknown'}",
        "",
        "Incident narrative:",
    ]
    for field in NARRATIVE_FIELDS:
        value = narratives.get(field)
        lines.append(f"- {_NARRATIVE_LABELS[field]}: {value or '(not provided)'}")
    lines.append("")
    lines.append(
        "Classify this incident by calling the classification tool with every field populated."
    )
    return "\n".join(lines)
