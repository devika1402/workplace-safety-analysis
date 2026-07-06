-- Singular test (PRD sections 5 and 8).
-- Fails if fewer than the configured fraction (var min_enrichment_coverage,
-- default 0.90) of narrated incidents received an LLM event category. Every row
-- in int_incidents__enriched is a narrated incident (staging filters out
-- all-null narratives), so the denominator is the row count. Returning any row
-- means coverage is below the threshold, which fails the test.

with coverage as (

    select
        count(*) as narrated_incidents,
        count(llm_event_category) as classified_incidents
    from {{ ref('int_incidents__enriched') }}

)

select
    narrated_incidents,
    classified_incidents,
    round(classified_incidents::numeric / nullif(narrated_incidents, 0), 4) as coverage
from coverage
where narrated_incidents > 0
    and classified_incidents::numeric / narrated_incidents
        < {{ var('min_enrichment_coverage', 0.90) }}
