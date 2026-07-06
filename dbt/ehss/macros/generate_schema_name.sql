{#
  Route models to clean, layered schemas (staging, intermediate, marts) instead
  of dbt's default "<target_schema>_<custom>" concatenation. A model's +schema
  config becomes its schema verbatim; models without one fall back to the target
  schema. The raw schema is created by ingestion, not by dbt.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
