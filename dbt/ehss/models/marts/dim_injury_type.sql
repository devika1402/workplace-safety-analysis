-- Injury type dimension, one row per distinct combination of outcome and the
-- OIICS nature, body part, and event codes. Materialized as a table.

with injury_types as (

    select
        outcome_code,
        oiics_nature_code,
        oiics_body_part_code,
        oiics_event_code,
        max(oiics_nature_label) as oiics_nature_label,
        max(oiics_body_part_label) as oiics_body_part_label,
        max(oiics_event_label) as oiics_event_label
    from {{ ref('int_incidents__joined') }}
    group by outcome_code, oiics_nature_code, oiics_body_part_code, oiics_event_code

)

select
    {{ dbt_utils.generate_surrogate_key([
        'outcome_code', 'oiics_nature_code', 'oiics_body_part_code', 'oiics_event_code'
    ]) }} as injury_type_id,
    case outcome_code
        when 1 then 'Death'
        when 2 then 'Days away from work'
        when 3 then 'Job transfer or restriction'
        when 4 then 'Other recordable'
        else 'Unknown'
    end as outcome,
    outcome_code,
    oiics_nature_code,
    oiics_nature_label,
    oiics_body_part_code,
    oiics_body_part_label,
    oiics_event_code,
    oiics_event_label
from injury_types
