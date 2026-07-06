-- Establishment dimension, one row per establishment. The raw size code is
-- inconsistent, so the employee_size_bucket is derived from the reliable
-- annual_average_employees count. Materialized as a table.

with establishments as (

    select * from {{ ref('stg_osha__establishments') }}

)

select
    establishment_id,
    establishment_name,
    company_name,
    ein,
    case
        when annual_average_employees is null then 'Unknown'
        when annual_average_employees < 50 then 'Small (under 50)'
        when annual_average_employees < 250 then 'Medium (50 to 249)'
        when annual_average_employees < 1000 then 'Large (250 to 999)'
        else 'Very large (1000 or more)'
    end as employee_size_bucket,
    case ownership_type_code
        when 1 then 'Private'
        when 2 then 'State government'
        when 3 then 'Local government'
        else 'Unknown'
    end as ownership_type
from establishments
