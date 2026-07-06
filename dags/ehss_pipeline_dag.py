"""Airflow DAG for the EHS&S Incident Intelligence Pipeline.

One DAG (ehss_incident_intelligence) wiring the full pipeline with the TaskFlow
API: download, load raw, dbt staging, LLM enrichment, dbt marts, dbt test, and a
run summary. Scheduled @daily but built to be triggered manually for the demo.

No credentials are hardcoded here. Database connection, the local LLM endpoint
and model, and every other setting are read from the environment via
config.settings (Pydantic Settings) inside each task, or by dbt from its own
environment. The local Ollama endpoint has no API key.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.decorators import dag, task

logger = logging.getLogger("airflow.task")

# Deployment paths inside the Airflow image (the project is mounted here and dbt
# lives in its own virtualenv). These are infrastructure paths, not secrets.
DBT_PROJECT_DIR = "/opt/airflow/project/dbt/ehss"
DBT_BIN = "/home/airflow/dbt-venv/bin/dbt"


def _dbt_command(arguments: str) -> str:
    """Return a shell command that runs dbt in the project dir with given args."""
    return f"set -euo pipefail; cd {DBT_PROJECT_DIR} && {DBT_BIN} {arguments}"


def _log_failure(context: dict[str, Any]) -> None:
    """on_failure_callback: log the failed task's context."""
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    logger.error(
        "Task failed: dag_id=%s task_id=%s run_id=%s exception=%s",
        getattr(task_instance, "dag_id", "unknown"),
        getattr(task_instance, "task_id", "unknown"),
        context.get("run_id", "unknown"),
        exception,
    )


default_args = {
    "owner": "devika",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": _log_failure,
}


@dag(
    dag_id="ehss_incident_intelligence",
    description="OSHA incident intelligence: ingest, model, enrich, evaluate.",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["ehss", "osha", "dbt", "llm"],
)
def ehss_incident_intelligence() -> None:
    """Define the end-to-end EHS&S incident intelligence pipeline."""

    @task
    def download_osha_data() -> str:
        """Fetch (or reuse) the OSHA Case Detail file. Idempotent."""
        from ingestion.download import fetch

        path = fetch()
        logger.info("OSHA case detail available at %s", path)
        return str(path)

    @task
    def load_raw_to_postgres() -> int:
        """Sample narrated rows and load them into the raw schema."""
        from ingestion.load_raw import load_raw
        from ingestion.sample import sample_case_detail

        sample_path = sample_case_detail()
        row_count = load_raw(sample_path)
        logger.info("Loaded %d rows into the raw schema", row_count)
        return row_count

    @task.bash
    def dbt_run_staging() -> str:
        """Build the dbt staging models so enrichment can read from them."""
        return _dbt_command("build --select staging")

    @task
    def llm_enrich_narratives() -> dict[str, int]:
        """Classify staged narratives with the local LLM and write results back."""
        from enrichment.enrich import run

        summary = run()
        logger.info("Enrichment summary: %s", summary)
        return summary

    @task.bash
    def dbt_build_marts() -> str:
        """Build the intermediate and mart layers with enrichment joined in."""
        return _dbt_command("build --select intermediate marts")

    @task.bash
    def dbt_test() -> str:
        """Run all dbt data-quality tests. The DAG fails here on a breach."""
        return _dbt_command("test")

    @task
    def report_run_summary() -> dict[str, float]:
        """Log fact row count, enrichment coverage, and the agreement rate."""
        from sqlalchemy import create_engine, text

        from config.settings import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url)
        marts = settings.marts_schema
        try:
            with engine.begin() as connection:
                fact_rows = connection.execute(
                    text(f'select count(*) from "{marts}".fct_incidents')
                ).scalar_one()
                coverage = connection.execute(
                    text(
                        f"""
                        select round(
                            100.0 * count(llm_event_category)
                            / nullif(count(*), 0), 1)
                        from "{marts}".fct_incidents
                        """
                    )
                ).scalar_one()
                agreement = connection.execute(
                    text(
                        f"""
                        select round(
                            100.0 * sum(incidents_in_agreement)
                            / nullif(sum(incidents_evaluated), 0), 1)
                        from "{marts}".mart_llm_eval
                        """
                    )
                ).scalar_one()
        finally:
            engine.dispose()

        logger.info("===== EHS&S pipeline run summary =====")
        logger.info("fct_incidents rows         : %s", fact_rows)
        logger.info("LLM enrichment coverage    : %s%%", coverage)
        logger.info("LLM vs OIICS agreement rate: %s%%", agreement)
        logger.info("======================================")
        return {
            "fact_rows": float(fact_rows),
            "enrichment_coverage_pct": float(coverage),
            "agreement_rate_pct": float(agreement),
        }

    # Task order (each task reads from the warehouse/settings, so the chain is
    # control flow, not XCom passing).
    download = download_osha_data()
    load = load_raw_to_postgres()
    staging = dbt_run_staging()
    enrich = llm_enrich_narratives()
    marts_build = dbt_build_marts()
    tests = dbt_test()
    summary = report_run_summary()

    download >> load >> staging >> enrich >> marts_build >> tests >> summary


ehss_incident_intelligence()
