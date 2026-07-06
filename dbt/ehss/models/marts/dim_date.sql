-- Date dimension, one row per distinct incident date. Materialized as a table.

with dates as (

    select distinct incident_date
    from {{ ref('int_incidents__joined') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['incident_date']) }} as date_id,
    incident_date as full_date,
    extract(year from incident_date)::int as year,
    extract(quarter from incident_date)::int as quarter,
    extract(month from incident_date)::int as month
from dates
