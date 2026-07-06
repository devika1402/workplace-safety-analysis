# Custom Airflow image for the EHS&S Incident Intelligence Pipeline.
#
# Extends the official Airflow image and installs the project runtime
# dependencies. dbt is installed into a separate virtualenv so its dependency
# pins cannot collide with Airflow's, which is the standard way to run dbt and
# Airflow in one image without a resolver fight.
FROM apache/airflow:2.10.4-python3.11

# Kept in sync with pyproject.toml [project.optional-dependencies].dbt.
ARG DBT_CORE_VERSION=1.9.1
ARG DBT_POSTGRES_VERSION=1.9.1

# Application runtime dependencies (config, ingestion, enrichment). The official
# image already ships Airflow itself, so requirements.txt deliberately excludes
# it. If a dependency ever conflicts with Airflow at build time, pin against the
# Airflow constraints file for this version instead of loosening the pins.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# dbt in its own virtualenv under a writable home path, exposed on PATH so the
# dbt CLI is callable from Airflow bash tasks.
RUN python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir \
        "dbt-core==${DBT_CORE_VERSION}" "dbt-postgres==${DBT_POSTGRES_VERSION}"

# Make the mounted project importable (from ingestion ..., from config ...) and
# put the dbt CLI on PATH. The dbt venv is appended (not prepended) so the
# Airflow python (which has the project runtime deps) stays the default
# interpreter while the dbt CLI is still resolvable.
ENV PYTHONPATH=/opt/airflow/project
ENV PATH=${PATH}:/home/airflow/dbt-venv/bin
