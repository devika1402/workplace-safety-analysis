"""Local LLM client wrapper (Ollama via the OpenAI-compatible API).

Forces structured output through a tool whose schema mirrors
IncidentClassification, validates the response with Pydantic, retries transient
errors with exponential backoff plus jitter (capped), and skips (never crashes
on) a row that fails so a single bad incident cannot kill the run.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, cast

import openai
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from config.settings import Settings, get_settings
from enrichment.prompt import SYSTEM_PROMPT
from enrichment.schemas import EventCategory, IncidentClassification

logger = logging.getLogger(__name__)

TOOL_NAME = "record_incident_classification"

# Accepted event_category values. An out-of-vocabulary value from a weaker model
# is coerced to "other" (honest abstention, as the prompt instructs) rather than
# failing the whole row, which would otherwise penalize coverage for a model
# slip that the prompt already has a defined fallback for.
_VALID_EVENT_VALUES = {member.value for member in EventCategory}

# Transient errors worth retrying. Everything else (bad request, validation) is
# logged and skipped without a retry.
_RETRYABLE_ERRORS: tuple[type[Exception], ...] = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)


def _inline_refs(node: Any, defs: dict[str, Any] | None = None) -> Any:
    """Inline JSON-schema $defs/$ref so the tool schema is self-contained.

    Some local tool-calling backends handle inline enum schemas more reliably
    than $ref indirection, so dereference everything up front.
    """
    if defs is None and isinstance(node, dict):
        defs = node.get("$defs", {})
    if isinstance(node, dict):
        if "$ref" in node:
            ref_name = node["$ref"].split("/")[-1]
            return _inline_refs(dict((defs or {})[ref_name]), defs)
        return {key: _inline_refs(value, defs) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def _tool_definition() -> ChatCompletionToolParam:
    """Build the tool definition mirroring IncidentClassification."""
    parameters = _inline_refs(IncidentClassification.model_json_schema())
    return cast(
        ChatCompletionToolParam,
        {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": (
                    "Record the structured safety classification of one incident narrative."
                ),
                "parameters": parameters,
            },
        },
    )


def build_client(settings: Settings | None = None) -> OpenAI:
    """Build an OpenAI client pointed at the local Ollama endpoint."""
    settings = settings or get_settings()
    return OpenAI(
        base_url=settings.ollama_base_url,
        api_key=settings.ollama_api_key,
        timeout=settings.llm_timeout_seconds,
    )


def _backoff_seconds(attempt: int, settings: Settings) -> float:
    """Return an exponential-backoff-with-full-jitter delay for an attempt."""
    capped = min(
        settings.llm_retry_max_seconds,
        settings.llm_retry_base_seconds * (2**attempt),
    )
    return random.uniform(0.0, capped)


def classify_narrative(
    client: OpenAI,
    user_prompt: str,
    *,
    incident_id: str,
    settings: Settings | None = None,
) -> IncidentClassification | None:
    """Classify one incident narrative, returning None if the row fails.

    Forces the classification tool, validates the tool arguments with Pydantic,
    and retries transient errors up to settings.llm_max_retries times. Any
    failure is logged with the incident_id and yields None (skip), never an
    exception that would end the run.
    """
    settings = settings or get_settings()
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    tools = [_tool_definition()]

    for attempt in range(settings.llm_max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.ollama_model,
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("model returned no tool call")
            data = json.loads(tool_calls[0].function.arguments)
            if isinstance(data, dict) and data.get("event_category") not in _VALID_EVENT_VALUES:
                logger.info(
                    "incident %s: coercing unrecognized event_category %r to 'other'",
                    incident_id,
                    data.get("event_category"),
                )
                data["event_category"] = EventCategory.other.value
            return IncidentClassification.model_validate(data)
        except _RETRYABLE_ERRORS as err:
            if attempt >= settings.llm_max_retries:
                logger.warning(
                    "incident %s: giving up after %d retries: %s",
                    incident_id,
                    settings.llm_max_retries,
                    err,
                )
                return None
            time.sleep(_backoff_seconds(attempt, settings))
        except Exception as err:
            logger.warning(
                "incident %s: classification failed and was skipped: %s",
                incident_id,
                err,
            )
            return None
    return None
