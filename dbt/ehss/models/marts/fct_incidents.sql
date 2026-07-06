-- Incident fact table. Grain: one row per reported OSHA case. Carries the
-- dimension foreign keys, the measures, the LLM enrichment columns, and the
-- narrative text for traceability. Materialized as a table.

with incidents as (

    select * from {{ ref('int_incidents__enriched') }}

)

select
    -- Primary key
    incident_id,

    -- Dimension foreign keys (surrogate keys match the dimension primary keys)
    establishment_id,
    {{ dbt_utils.generate_surrogate_key(['naics_code']) }} as industry_id,
    {{ dbt_utils.generate_surrogate_key(['city', 'state', 'zip_code']) }} as geography_id,
    {{ dbt_utils.generate_surrogate_key([
        'outcome_code', 'oiics_nature_code', 'oiics_body_part_code', 'oiics_event_code'
    ]) }} as injury_type_id,
    {{ dbt_utils.generate_surrogate_key(['incident_date']) }} as date_id,

    -- Measures
    days_away_from_work,
    days_restricted,
    is_death,
    is_dafw,

    -- Outcome and OIICS event, kept on the fact for the evaluation
    outcome_code,
    oiics_event_code,
    oiics_event_label,
    incident_date,

    -- LLM enrichment carried onto the fact for easy querying
    llm_contributing_factor,
    llm_severity_tier,
    llm_recurrence_action,
    llm_event_category,
    llm_confidence,

    -- Narrative text for traceability back to the source story
    narrative_location,
    narrative_description,
    narrative_activity,
    narrative_event,
    narrative_injury,
    narrative_source
from incidents
