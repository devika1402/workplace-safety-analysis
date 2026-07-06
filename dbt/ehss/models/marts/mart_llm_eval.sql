-- LLM-versus-OIICS evaluation. For each incident that has both an LLM event
-- category and an OIICS event code, both are mapped to a common coarse event
-- taxonomy and compared. The result is an agreement rate per industry sector and
-- severity tier: a real, defensible number for how often the local model agreed
-- with the BLS autocoder on the same narratives. Materialized as a table.

with scored as (

    select
        coalesce(industry.sector, 'Unknown') as sector,
        coalesce(fct.llm_severity_tier, 'unknown') as severity_tier,
        case
            when {{ coarse_event_from_llm('fct.llm_event_category') }}
                = {{ coarse_event_from_oiics('fct.oiics_event_code') }}
            then 1
            else 0
        end as is_agreement
    from {{ ref('fct_incidents') }} fct
    left join {{ ref('dim_industry') }} industry
        on fct.industry_id = industry.industry_id
    where fct.llm_event_category is not null
        and fct.oiics_event_code is not null

)

select
    {{ dbt_utils.generate_surrogate_key(['sector', 'severity_tier']) }} as eval_id,
    sector,
    severity_tier,
    count(*) as incidents_evaluated,
    sum(is_agreement) as incidents_in_agreement,
    round(avg(is_agreement::numeric), 4) as agreement_rate
from scored
group by sector, severity_tier
