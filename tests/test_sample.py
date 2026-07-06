"""Unit tests for ingestion.sample."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from config.settings import Settings
from ingestion.sample import sample_case_detail


def _settings(tmp_path: Path, **kwargs: object) -> Settings:
    return Settings(raw_data_dir=tmp_path, sampled_csv_filename="sample_out.csv", **kwargs)


def test_sample_matches_columns_case_insensitively(tmp_path: Path) -> None:
    src = tmp_path / "src.csv"
    pd.DataFrame({"NEW_NAR_WHAT_HAPPENED": ["fell", None, "cut"], "other": [1, 2, 3]}).to_csv(
        src, index=False
    )
    # Configured lowercase; real header is uppercase. Matching must still work.
    settings = _settings(tmp_path, narrative_columns=("new_nar_what_happened",), sample_size=10)

    result = pd.read_csv(sample_case_detail(source_path=src, settings=settings))

    # Only the two rows with a non-null narrative survive.
    assert len(result) == 2


def test_sample_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "src.csv"
    pd.DataFrame({"NEW_NAR_WHAT_HAPPENED": [f"n{i}" for i in range(100)]}).to_csv(src, index=False)
    settings = _settings(
        tmp_path,
        narrative_columns=("NEW_NAR_WHAT_HAPPENED",),
        sample_size=5,
        sample_random_seed=7,
    )

    first = pd.read_csv(sample_case_detail(source_path=src, settings=settings))
    second = pd.read_csv(sample_case_detail(source_path=src, settings=settings))

    assert len(first) == 5
    assert list(first["NEW_NAR_WHAT_HAPPENED"]) == list(second["NEW_NAR_WHAT_HAPPENED"])


def test_sample_raises_when_no_narrative_columns(tmp_path: Path) -> None:
    src = tmp_path / "src.csv"
    pd.DataFrame({"foo": [1], "bar": [2]}).to_csv(src, index=False)
    settings = _settings(tmp_path, narrative_columns=("NEW_NAR_WHAT_HAPPENED",))

    with pytest.raises(ValueError):
        sample_case_detail(source_path=src, settings=settings)
