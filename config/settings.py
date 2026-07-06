"""Application configuration for the EHS&S Incident Intelligence Pipeline.

This module is the single source of truth for every configurable value in the
project. Per the project rules, no magic constants live inside function bodies:
anything tunable is declared here as a typed, documented setting and read from
the environment (or the .env file) at runtime.

All settings use Pydantic v2 (pydantic-settings) so values are validated and
type coerced on load, and a misconfiguration fails loudly at startup rather
than deep inside a task.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, derived from this file location (config/settings.py). Used to
# anchor default filesystem paths so the project is runnable from a clean clone
# without further configuration.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed, validated configuration loaded from the environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg2://ehss:ehss@localhost:5432/ehss",
        description=(
            "SQLAlchemy connection URL for the Postgres warehouse. Inside the "
            "Docker network the host is 'postgres'; from the host machine it is "
            "'localhost'."
        ),
    )
    raw_schema: str = Field(
        default="raw",
        description="Postgres schema that holds untyped landed data.",
    )
    case_detail_table: str = Field(
        default="osha_case_detail",
        description="Raw table name for OSHA case detail rows (Forms 300 and 301).",
    )
    establishments_table: str = Field(
        default="osha_establishments",
        description="Raw table name for OSHA establishment (300A) rows.",
    )
    staging_schema: str = Field(
        default="staging",
        description="Schema where dbt builds the staging views.",
    )
    marts_schema: str = Field(
        default="marts",
        description="Schema where dbt builds the mart tables.",
    )
    llm_enrichment_table: str = Field(
        default="llm_enrichment",
        description="Table in the raw schema holding LLM classifications.",
    )
    llm_cache_table: str = Field(
        default="llm_cache",
        description="Table in the raw schema caching classifications by narrative hash.",
    )

    # --- OSHA data source ---
    osha_data_url: str = Field(
        default="",
        description=(
            "Direct download URL for the OSHA ITA Case Detail file. Empty by "
            "default because the ITA Data page renders its download links with "
            "JavaScript, so they cannot be fetched programmatically. Download the "
            "CY2024 Case Detail file by hand from the ITA Data page "
            "(https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data) "
            "and place it at case_detail_download_path, or set this to a direct "
            "file URL if one is available. The download step reuses an existing "
            "local file."
        ),
    )
    raw_data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Local directory where the source and sampled files live.",
    )
    osha_case_detail_filename: str = Field(
        default="ITA_Case_Detail_Data_2024_through_12-31-2025.csv",
        description=(
            "Local filename of the OSHA Case Detail file (the CY2024 file "
            "downloaded by hand). Plain CSV, Windows-1252 encoded."
        ),
    )
    sampled_csv_filename: str = Field(
        default="osha_case_detail_sample.csv",
        description="Local filename for the deterministic sampled subset.",
    )
    narrative_columns: tuple[str, ...] = Field(
        default=(
            "NEW_INCIDENT_LOCATION",
            "NEW_INCIDENT_DESCRIPTION",
            "NEW_NAR_BEFORE_INCIDENT",
            "NEW_NAR_WHAT_HAPPENED",
            "NEW_NAR_INJURY_ILLNESS",
            "NEW_NAR_OBJECT_SUBSTANCE",
        ),
        description=(
            "Raw CSV column names holding incident narrative free text, as "
            "published in the CY2024 file (uppercase NEW_ headers). Six fields: "
            "two from Form 300 (location, description) and four from Form 301 "
            "(before, what happened, injury, object or substance). The NEW_ "
            "prefix marks the PII-stripped public versions. Matching is case "
            "insensitive; sampling keeps rows where at least one is non-null; the "
            "staging layer renames them to narrative_* names."
        ),
    )
    csv_encoding: str = Field(
        default="cp1252",
        description=(
            "Text encoding of the source CSV. OSHA exports are Windows-1252; use "
            "latin-1 if cp1252 ever fails on an undefined byte."
        ),
    )
    csv_encoding_errors: str = Field(
        default="replace",
        description=(
            "Decode error policy for the source CSV (pandas encoding_errors). "
            "'replace' tolerates the rare undefined byte in the free text."
        ),
    )

    # --- Sampling ---
    sample_size: int = Field(
        default=1000,
        ge=1,
        description="Number of narrated rows to keep in the demo sample.",
    )
    sample_random_seed: int = Field(
        default=42,
        description="Fixed seed so sampling is reproducible across runs and CI.",
    )

    # --- Download behaviour ---
    download_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        description="Per-request timeout for the OSHA download, in seconds.",
    )
    download_chunk_size: int = Field(
        default=1 << 20,
        ge=1,
        description="Streaming chunk size for the download, in bytes (1 MiB).",
    )

    # --- LLM enrichment (local Ollama, OpenAI-compatible API) ---
    # Ollama runs models locally with no API key, no account, and no spend.
    # The tradeoff is that it needs a decent laptop and runs slower, and model
    # quality is lower than a hosted frontier model, so the mart_llm_eval
    # agreement rate will be lower.
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL of the local Ollama OpenAI-compatible API.",
    )
    ollama_api_key: str = Field(
        default="ollama",
        description=(
            "Placeholder API key for the OpenAI client. Ollama ignores its "
            "value, but the OpenAI SDK requires a non-empty string."
        ),
    )
    ollama_model: str = Field(
        default="llama3.1",
        description="Local Ollama model id used for narrative enrichment.",
    )
    llm_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        description="Per-request timeout for the local LLM, in seconds.",
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        description="Sampling temperature for the LLM (0 for deterministic output).",
    )
    llm_max_tokens: int = Field(
        default=1024,
        ge=1,
        description="Maximum number of tokens in the LLM response.",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retries on transient LLM errors.",
    )
    llm_retry_base_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Base delay for exponential backoff between retries, in seconds.",
    )
    llm_retry_max_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum backoff delay between retries, in seconds.",
    )
    prompt_version: str = Field(
        default="v1",
        description=(
            "Version tag for the enrichment prompt, stored alongside every "
            "enrichment row so outputs are traceable to the prompt that made "
            "them."
        ),
    )
    enrichment_batch_size: int = Field(
        default=20,
        ge=1,
        description=(
            "Number of incidents to process per enrichment work unit. The client "
            "defaults to one API call per incident for correctness; this controls "
            "how rows are grouped for logging and progress reporting."
        ),
    )
    min_enrichment_coverage: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum fraction of narrated incidents that must receive an LLM "
            "classification. The dbt singular test fails below this threshold."
        ),
    )

    @property
    def case_detail_download_path(self) -> Path:
        """Return the absolute path to the downloaded Case Detail archive."""
        return self.raw_data_dir / self.osha_case_detail_filename

    @property
    def sampled_csv_path(self) -> Path:
        """Return the absolute path to the deterministic sampled CSV."""
        return self.raw_data_dir / self.sampled_csv_filename


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, validated settings instance.

    Using a cache means the environment is read and validated once per process.
    Tests can clear the cache with get_settings.cache_clear() to load overrides.
    """
    return Settings()


# Module level convenience instance for straightforward imports.
settings: Settings = get_settings()
