-- Merge LLM enrichment onto the joined incidents. This is the seam: a left join
-- means incidents that have not been enriched still flow through with null
-- enrichment columns, so the warehouse degrades gracefully.

with joined as (

    select * from {{ ref('int_incidents__joined') }}

),

enrichment as (

    select * from {{ ref('stg_llm__enrichment') }}

)

select
    joined.*,
    enrichment.llm_contributing_factor,
    enrichment.llm_severity_tier,
    enrichment.llm_event_category,
    enrichment.llm_recurrence_action,
    enrichment.llm_confidence,
    enrichment.prompt_version as llm_prompt_version,
    enrichment.model_name as llm_model_name,
    enrichment.enriched_at as llm_enriched_at
from joined
left join enrichment on joined.incident_id = enrichment.incident_id
