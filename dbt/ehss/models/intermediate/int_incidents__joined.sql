-- Join case detail to establishment attributes: one row per incident with its
-- establishment context resolved. Establishment-level fields (name, address,
-- industry, geography, size) come from the establishment model so they are the
-- canonical, deduplicated values; incident-level fields come from case detail.

with incidents as (

    select * from {{ ref('stg_osha__case_detail') }}

),

establishments as (

    select * from {{ ref('stg_osha__establishments') }}

)

select
    -- Incident keys and case attributes
    i.incident_id,
    i.osha_case_id,
    i.case_number,
    i.establishment_id,
    i.incident_date,
    i.death_date,
    i.created_at,
    i.filing_year,
    i.outcome_code,
    i.incident_type_code,
    i.days_away_from_work,
    i.days_restricted,
    i.is_death,
    i.is_dafw,
    i.soc_code,
    i.soc_description,
    i.job_description,

    -- Establishment context (canonical, from the establishment model)
    e.establishment_name,
    e.company_name,
    e.ein,
    e.street_address,
    e.city,
    e.state,
    e.zip_code,
    e.naics_code,
    e.naics_year,
    e.industry_description,
    e.ownership_type_code,
    e.employee_size_code,
    e.annual_average_employees,
    e.total_hours_worked,

    -- Narratives (kept for traceability)
    i.narrative_location,
    i.narrative_description,
    i.narrative_activity,
    i.narrative_event,
    i.narrative_injury,
    i.narrative_source,

    -- OIICS autocoder ground truth
    i.oiics_nature_code,
    i.oiics_nature_label,
    i.oiics_body_part_code,
    i.oiics_body_part_label,
    i.oiics_event_code,
    i.oiics_event_label,
    i.oiics_source_code,
    i.oiics_source_label,
    i.oiics_sec_source_code,
    i.oiics_sec_source_label
from incidents i
left join establishments e on i.establishment_id = e.establishment_id
