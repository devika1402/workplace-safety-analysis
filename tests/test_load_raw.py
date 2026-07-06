"""Unit tests for ingestion.load_raw."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine

from config.settings import Settings
from ingestion.load_raw import load_raw, snake_case_columns


def test_snake_case_columns_normalizes_names() -> None:
    result = snake_case_columns(["Establishment Name", "NAICS-Code", "Days Away From Work", "id"])
    assert result == [
        "establishment_name",
        "naics_code",
        "days_away_from_work",
        "id",
    ]


def test_snake_case_columns_rejects_empty_result() -> None:
    with pytest.raises(ValueError):
        snake_case_columns(["???"])


def test_load_raw_writes_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame({"Establishment Name": ["Acme", "Globex"], "NAICS Code": [3361, 5417]}).to_csv(
        csv_path, index=False
    )

    engine = create_engine("sqlite://")
    settings = Settings(case_detail_table="osha_case_detail")

    count = load_raw(sampled_path=csv_path, settings=settings, engine=engine)

    assert count == 2
    loaded = pd.read_sql("SELECT * FROM osha_case_detail", engine)
    assert list(loaded.columns) == ["establishment_name", "naics_code"]
    assert len(loaded) == 2
    engine.dispose()


def test_load_raw_replaces_on_rerun(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame({"Col A": [1, 2, 3]}).to_csv(csv_path, index=False)
    engine = create_engine("sqlite://")
    settings = Settings(case_detail_table="osha_case_detail")

    first = load_raw(sampled_path=csv_path, settings=settings, engine=engine)
    second = load_raw(sampled_path=csv_path, settings=settings, engine=engine)

    assert first == second == 3
    loaded = pd.read_sql("SELECT * FROM osha_case_detail", engine)
    assert len(loaded) == 3
    engine.dispose()


def test_load_raw_missing_file_raises(tmp_path: Path) -> None:
    settings = Settings()
    engine = create_engine("sqlite://")
    with pytest.raises(FileNotFoundError):
        load_raw(sampled_path=tmp_path / "nope.csv", settings=settings, engine=engine)
    engine.dispose()
