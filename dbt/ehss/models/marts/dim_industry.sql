-- Industry dimension, one row per NAICS code. Sector is derived from the first
-- two NAICS digits. Materialized as a table.

with industries as (

    select
        naics_code,
        max(industry_description) as industry_description
    from {{ ref('int_incidents__joined') }}
    group by naics_code

)

select
    {{ dbt_utils.generate_surrogate_key(['naics_code']) }} as industry_id,
    naics_code,
    industry_description as naics_title,
    {{ naics_sector('naics_code') }} as sector
from industries
