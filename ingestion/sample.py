"""Deterministically sample narrated rows from the downloaded Case Detail file.

The full Case Detail file is large; the demo runs over a fixed-size sample so the
LLM step finishes in a sensible time. Sampling uses a fixed seed so local runs
and CI are reproducible.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _present_narrative_columns(frame: pd.DataFrame, candidates: tuple[str, ...]) -> list[str]:
    """Return the configured narrative columns that exist in the frame.

    Args:
        frame: The loaded source data.
        candidates: Configured narrative column names to look for.

    Returns:
        The actual frame column names (real case) matching the candidates,
        compared case insensitively. The OSHA file uses uppercase NEW_ headers,
        but matching does not depend on the configured case.

    Raises:
        ValueError: If none of the configured columns are present, which means
            the configuration does not match the source file.
    """
    lookup = {str(column).lower(): str(column) for column in frame.columns}
    present = [lookup[name.lower()] for name in candidates if name.lower() in lookup]
    if not present:
        raise ValueError(
            f"None of the configured narrative columns {candidates} are present "
            f"in the source file (matched case insensitively). Available "
            f"columns: {list(frame.columns)}. Update settings.narrative_columns "
            "to match the published file."
        )
    return present


def sample_case_detail(source_path: Path | None = None, settings: Settings | None = None) -> Path:
    """Write a deterministic sample of narrated rows to CSV and return its path.

    Reads the downloaded Case Detail file (CSV, optionally zip compressed), keeps
    only rows where at least one narrative column is non-null, then takes a fixed
    seed sample of up to settings.sample_size rows.

    Args:
        source_path: Path to the downloaded Case Detail file. Falls back to the
            configured download path.
        settings: Configuration to use. Falls back to the process settings.

    Returns:
        The path to the written sample CSV.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If no narrated rows remain after filtering.
    """
    settings = settings or get_settings()
    source_path = source_path or settings.case_detail_download_path
    if not source_path.exists():
        raise FileNotFoundError(
            f"Case detail source not found at {source_path}. Run the download step first."
        )

    logger.info("Reading case detail from %s", source_path)
    # Read as text to preserve source values exactly (leading zeros, date strings)
    # and to keep landed types stable. Casting happens in the dbt staging layer.
    frame = pd.read_csv(
        source_path,
        compression="infer",
        low_memory=False,
        dtype=str,
        encoding=settings.csv_encoding,
        encoding_errors=settings.csv_encoding_errors,
    )

    narrative_cols = _present_narrative_columns(frame, settings.narrative_columns)
    narrated = frame.dropna(subset=narrative_cols, how="all")
    if narrated.empty:
        raise ValueError("No rows with a non-null narrative were found; nothing to enrich.")

    sample_n = min(settings.sample_size, len(narrated))
    sampled = narrated.sample(n=sample_n, random_state=settings.sample_random_seed)

    target = settings.sampled_csv_path
    target.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_csv(target, index=False)
    logger.info("Wrote %d sampled rows to %s", len(sampled), target)
    return target
