# Workplace Safety Analysis Pipeline

This project reads workplace-injury reports at scale. Every year, big employers send the US government a record of every serious injury at their workplaces, and since 2024 each one carries a short written account of what the worker was doing and what went wrong. Hundreds of thousands arrive as messy free text, far too many to read by hand.

It takes 688,649 OSHA injury records, models them into a Postgres star schema, and runs every narrative through a language model that pulls out a contributing factor, a severity tier, and a preventive action. Each extraction is scored against the government's own classification code for the same incident, so the result is a warehouse a query can join against, with the model's reliability measured against a published standard.

![Workplace safety pipeline: injury data is downloaded, loaded into the database, cleaned and organised, read narrative by narrative by a language model, built into a warehouse, scored against government codes, checked for quality, and reported as a coverage and agreement summary, all run as one Airflow pipeline](docs/diagrams/architecture.png)

The build is a straight line with one branch. The raw file arrives in Postgres exactly as downloaded, gets staged and enriched narrative by narrative, and is written into a star schema a query can join against like any other warehouse. Off that same schema, one mart scores the enrichment against the government code, split by industry sector and severity. Every step runs as an Airflow task, and 50 dbt tests plus 31 pytest unit tests gate the build in CI before any of it reaches the warehouse.

There is no real-time serving and no dashboard here, on purpose. This project stops at a queryable warehouse and a scored evaluation mart.

## Why I built this

I built this in June 2026 to work on two things: Airflow orchestration, and evaluating LLM output against a published standard. The platform side uses Airflow, dbt, and Postgres. The domain side uses OIICS classification and a model-versus-autocoder agreement check.

## At a glance

| | |
|---|---|
| Data | 688,649 OSHA ITA injury records (2024 onward), each with a free-text incident narrative |
| Pipeline | raw load into Postgres, dbt staging and intermediate models, a star schema of `fct_incidents` and five dimensions |
| Enrichment | Ollama (llama3.1) reads each narrative and returns a contributing factor, a severity tier, and a preventive action, as structured output |
| Evaluation | each enrichment compared against the BLS autocoder's OIICS code in `mart_llm_eval`, agreement split by industry sector and severity |
| Data quality | 50 dbt tests and 31 pytest unit tests gate the build. A coverage test stops the run if under 90% of narrated incidents are classified |
| Orchestration | one 7-task Airflow DAG: download, load, stage, enrich, build marts, test, summarise |
| Stack | Airflow (LocalExecutor), dbt-core with Postgres, Ollama, Pydantic, GitHub Actions |

## Run it

Requires Docker and a local Ollama install. No API key, no account.

```bash
git clone <repo> && cd workplace-safety-analysis
cp .env.example .env
# open .env and confirm the OSHA download link from the ITA Data page

ollama pull llama3.1
docker compose up -d
```

Open http://localhost:8080, turn on the `ehss_incident_intelligence` DAG, and trigger it. It downloads the data, loads it, stages and enriches every narrative, builds the marts, runs the tests, and prints a summary with the coverage rate and the LLM-versus-OIICS agreement rate.

```bash
docker compose exec postgres psql -U ehss -d ehss
# select * from marts.fct_incidents limit 10;
# select * from marts.mart_llm_eval;
```

## The pipeline stages, and why each boundary exists

- **Staging** (`stg_osha__case_detail`, `stg_osha__establishments`) is the raw file typed and renamed, one to one with the source columns.
- **Enrichment** (`stg_llm__enrichment`) is where Ollama reads each narrative and returns a contributing factor, a severity tier, and a preventive action, forced into a Pydantic schema so the model cannot drift into freeform text. A response cache keyed on the narrative means a re-run never re-pays for an unchanged row.
- **Intermediate** (`int_incidents__joined`, `int_incidents__enriched`) joins the case detail to the establishment record and to the enrichment output, one row per incident.
- **Marts** (`fct_incidents` plus `dim_date`, `dim_establishment`, `dim_geography`, `dim_industry`, `dim_injury_type`) is the star schema a query joins against directly.
- **Eval mart** (`mart_llm_eval`) maps the LLM's event category and the OIICS code onto a shared coarse taxonomy, compares them, and reports agreement by sector and severity tier. This is a model-against-model check, scored against a recognised government standard rather than human-coded ground truth.

## dbt tests gate the build

A failing test fails the build. The suite is 50 tests: `unique` and `not_null` on keys, `relationships` on every fact-to-dimension foreign key, `accepted_values` on enums, dbt-expectations range checks, and a singular coverage test that fails the run if under 90% of narrated incidents received an LLM classification. 31 pytest unit tests cover the download, the raw load, the prompt construction, the enrichment client, and the Pydantic schemas. CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs ruff, mypy, and the full test suite on every push, against committed fixtures rather than the model or the OSHA file directly.

## Scope

- The agreement rate is a model-against-model number. The OIICS codes come from the BLS autocoder rather than a human coder, so a high agreement rate still falls short of a verified-correct rate.
- The enrichment runs on a small local model through Ollama, which is less accurate than a hosted frontier model. That is the price of no API key and no cost.
- The OSHA download is manual. The ITA Data page gates the file behind a browser step, so the link goes in `.env` and is confirmed by hand before the first run.

## Built with

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Airflow](https://img.shields.io/badge/Airflow-orchestration-017CEE?logo=apacheairflow&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-transform-FF694B?logo=dbt&logoColor=white)
![Postgres](https://img.shields.io/badge/Postgres-warehouse-4169E1?logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-llama3.1-000000?logo=ollama&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-validation-E92063?logo=pydantic&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-tests-0A9EDC?logo=pytest&logoColor=white)
![ruff](https://img.shields.io/badge/ruff-lint-261230)
![mypy](https://img.shields.io/badge/mypy-typed-2A6DB2)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI-2088FF?logo=githubactions&logoColor=white)

Postgres for a warehouse that runs locally with no cloud account, Airflow for a dependency graph that retries a failed step and shows where a run stopped, dbt for SQL that is version-controlled and tested the way any other code is, Ollama for enrichment with no API key and no spend, and Pydantic to force every LLM response into a fixed schema.

## Data

Public OSHA injury records, reported by employers and published by the agency. The download link is on the [OSHA ITA Data page](https://www.osha.gov/Establishment-Specific-Injury-and-Illness-Data), and the field definitions are in their [data users guide](https://www.osha.gov/sites/default/files/ITA_data_users_guide.pdf).
