-- Staging model for the establishment entity, one row per establishment.
-- There is no separate OSHA establishments file; establishment attributes are
-- columns on the case detail source, so this deduplicates them to one row per
-- establishment and builds a stable establishment_id surrogate key.

with source as (

    select * from {{ source('osha', 'osha_case_detail') }}

),

deduplicated as (

    select
        establishment_id,
        establishment_name,
        company_name,
        ein,
        street_address,
        city,
        state,
        zip_code,
        naics_code,
        naics_year,
        industry_description,
        establishment_type,
        size,
        annual_average_employees,
        total_hours_worked,
        row_number() over (
            partition by establishment_id
            order by created_timestamp desc nulls last
        ) as row_num
    from source
    where establishment_id is not null

),

renamed as (

    select
        {{ dbt_utils.generate_surrogate_key(['establishment_id']) }} as establishment_id,
        cast(establishment_id as bigint) as osha_establishment_id,
        nullif(trim(establishment_name), '') as establishment_name,
        nullif(trim(company_name), '') as company_name,
        nullif(trim(ein), '') as ein,
        nullif(trim(street_address), '') as street_address,
        nullif(trim(city), '') as city,
        nullif(trim(state), '') as state,
        nullif(trim(zip_code), '') as zip_code,
        nullif(trim(naics_code), '') as naics_code,
        nullif(trim(naics_year), '')::integer as naics_year,
        nullif(trim(industry_description), '') as industry_description,
        nullif(trim(establishment_type), '')::numeric::integer as ownership_type_code,
        nullif(trim(size), '')::numeric::integer as employee_size_code,
        nullif(trim(annual_average_employees), '')::numeric::integer as annual_average_employees,
        nullif(trim(total_hours_worked), '')::numeric::bigint as total_hours_worked
    from deduplicated
    where row_num = 1

)

select * from renamed
