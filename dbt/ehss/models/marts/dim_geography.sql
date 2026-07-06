-- Geography dimension, one row per distinct city/state/zip. Region maps the
-- state to a US census region. Materialized as a table.

with geographies as (

    select distinct
        city,
        state,
        zip_code
    from {{ ref('int_incidents__joined') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['city', 'state', 'zip_code']) }} as geography_id,
    city,
    state,
    zip_code,
    {{ census_region('state') }} as region
from geographies
