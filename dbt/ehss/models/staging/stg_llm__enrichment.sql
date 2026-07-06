-- Staging view over the raw LLM enrichment output, one row per classified
-- incident. Renames columns to llm_* names for the marts. The raw table is
-- already typed (written by the enrichment step), so this only renames and
-- trims text.

with source as (

    select * from {{ source('osha', 'llm_enrichment') }}

),

renamed as (

    select
        incident_id,
        nullif(trim(contributing_factor), '') as llm_contributing_factor,
        nullif(trim(severity_tier), '') as llm_severity_tier,
        nullif(trim(event_category), '') as llm_event_category,
        nullif(trim(recurrence_prevention), '') as llm_recurrence_action,
        confidence as llm_confidence,
        prompt_version,
        model_name,
        enriched_at
    from source

)

select * from renamed
