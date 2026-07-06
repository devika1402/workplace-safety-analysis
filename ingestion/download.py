"""Download the OSHA ITA Case Detail file into the local raw data directory.

The download URL is configurable (see config.settings); this module never hard
codes a source URL in a function body. The fetch is idempotent: an existing,
non-empty local file is reused unless a re-download is forced.

In practice the OSHA ITA Data page renders its download links with JavaScript,
so they cannot be fetched programmatically. The common path is therefore to
download the Case Detail file by hand and drop it in the raw data directory; the
idempotent reuse below then picks it up without any network call.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def fetch(settings: Settings | None = None, *, force: bool = False) -> Path:
    """Download the configured OSHA Case Detail file and return its local path.

    Streams the response to disk so the whole archive is never held in memory.
    Raises on any HTTP error and on an empty download, so failures are loud.

    Args:
        settings: Configuration to use. Falls back to the process settings.
        force: Re-download even if a non-empty local copy already exists.

    Returns:
        The path to the downloaded file on disk.

    Raises:
        requests.HTTPError: If the server returns a non-success status code.
        RuntimeError: If no local file exists and no URL is configured, or if
            the downloaded file is unexpectedly empty.
    """
    settings = settings or get_settings()
    target: Path = settings.case_detail_download_path
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and target.stat().st_size > 0 and not force:
        logger.info("Reusing existing download at %s", target)
        return target

    if not settings.osha_data_url:
        raise RuntimeError(
            f"No Case Detail file at {target} and OSHA_DATA_URL is not set. The "
            "OSHA ITA Data page renders its download links with JavaScript, so "
            "they cannot be fetched programmatically. Download the CY2024 Case "
            "Detail file by hand from "
            "https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data "
            f"and place it at {target}, or set OSHA_DATA_URL to a direct file URL."
        )

    logger.info("Downloading OSHA case detail from %s", settings.osha_data_url)
    response = requests.get(
        settings.osha_data_url,
        stream=True,
        timeout=settings.download_timeout_seconds,
    )
    response.raise_for_status()

    with target.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=settings.download_chunk_size):
            if chunk:
                handle.write(chunk)

    size = target.stat().st_size
    if size == 0:
        raise RuntimeError(
            f"Downloaded file at {target} is empty; the source URL "
            f"({settings.osha_data_url}) may be wrong or the response truncated."
        )

    logger.info("Saved %d bytes to %s", size, target)
    return target
