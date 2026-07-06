-- Staging model for OSHA case detail (one row per reported case).
-- Reads the untyped raw source, casts dates/measures, renames the six narrative
-- fields, surfaces the OIICS autocoder (_pred) fields, builds a stable
-- incident_id surrogate key, and drops rows with no narrative to enrich.

with source as (

    select * from {{ source('osha', 'osha_case_detail') }}

),

renamed as (

    select
        -- Keys
        {{ dbt_utils.generate_surrogate_key(['id']) }} as incident_id,
        cast(id as bigint) as osha_case_id,
        nullif(trim(case_number), '') as case_number,
        {{ dbt_utils.generate_surrogate_key(['establishment_id']) }} as establishment_id,

        -- Dates and timestamps (SAS DDMONYYYY format in the source)
        to_date(nullif(trim(date_of_incident), ''), 'DDMONYYYY') as incident_date,
        to_date(nullif(trim(date_of_death), ''), 'DDMONYYYY') as death_date,
        to_timestamp(nullif(trim(created_timestamp), ''), 'DDMONYYYY:HH24:MI:SS') as created_at,
        nullif(trim(year_of_filing), '')::integer as filing_year,

        -- Outcome and measures
        nullif(trim(incident_outcome), '')::integer as outcome_code,
        nullif(trim(type_of_incident), '')::integer as incident_type_code,
        nullif(trim(dafw_num_away), '')::numeric::integer as days_away_from_work,
        nullif(trim(djtr_num_tr), '')::numeric::integer as days_restricted,
        (nullif(trim(incident_outcome), '')::integer = 1) as is_death,
        (nullif(trim(incident_outcome), '')::integer = 2) as is_dafw,

        -- Occupation
        nullif(trim(soc_code), '') as soc_code,
        nullif(trim(soc_description), '') as soc_description,
        nullif(trim(job_description), '') as job_description,

        -- Industry and geography (carried for the downstream dimensions)
        nullif(trim(naics_code), '') as naics_code,
        nullif(trim(industry_description), '') as industry_description,
        nullif(trim(city), '') as city,
        nullif(trim(state), '') as state,
        nullif(trim(zip_code), '') as zip_code,

        -- Establishment context (carried for the intermediate join)
        nullif(trim(establishment_name), '') as establishment_name,
        nullif(trim(company_name), '') as company_name,

        -- Narratives: six free-text fields renamed to clear names
        nullif(trim(new_incident_location), '') as narrative_location,
        nullif(trim(new_incident_description), '') as narrative_description,
        nullif(trim(new_nar_before_incident), '') as narrative_activity,
        nullif(trim(new_nar_what_happened), '') as narrative_event,
        nullif(trim(new_nar_injury_illness), '') as narrative_injury,
        nullif(trim(new_nar_object_substance), '') as narrative_source,

        -- OIICS ground truth from the BLS SOII autocoder (_pred columns)
        nullif(trim(nature_code_pred), '')::numeric::integer as oiics_nature_code,
        nullif(trim(nature_title_pred), '') as oiics_nature_label,
        nullif(trim(part_code_pred), '')::numeric::integer as oiics_body_part_code,
        nullif(trim(part_title_pred), '') as oiics_body_part_label,
        nullif(trim(event_code_pred), '')::numeric::integer as oiics_event_code,
        nullif(trim(event_title_pred), '') as oiics_event_label,
        nullif(trim(source_code_pred), '')::numeric::integer as oiics_source_code,
        nullif(trim(source_title_pred), '') as oiics_source_label,
        nullif(trim(sec_source_code_pred), '')::numeric::integer as oiics_sec_source_code,
        nullif(trim(sec_source_title_pred), '') as oiics_sec_source_label

    from source

)

select *
from renamed
where coalesce(
    narrative_location,
    narrative_description,
    narrative_activity,
    narrative_event,
    narrative_injury,
    narrative_source
) is not null
