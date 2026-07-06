-- Committed CI fixture: a handful of fake OSHA case-detail rows and fake LLM
-- enrichment rows seeded into the raw schema so the dbt layer can build and test
-- with no live OSHA download and no LLM call.
--
-- Columns and value formats mirror what ingestion.load_raw lands (all text, SAS
-- date strings). The enrichment incident_id values are md5(id), which equals the
-- surrogate key dbt computes in stg_osha__case_detail, so coverage is 100%.

CREATE SCHEMA IF NOT EXISTS raw;

DROP TABLE IF EXISTS raw.osha_case_detail CASCADE;
DROP TABLE IF EXISTS raw.llm_enrichment CASCADE;

CREATE TABLE raw.osha_case_detail (
    id text, establishment_id text, establishment_name text, ein text,
    company_name text, street_address text, city text, state text, zip_code text,
    naics_code text, naics_year text, industry_description text,
    establishment_type text, size text, annual_average_employees text,
    total_hours_worked text, case_number text, job_description text,
    soc_code text, soc_description text, date_of_incident text, date_of_death text,
    created_timestamp text, year_of_filing text, incident_outcome text,
    type_of_incident text, dafw_num_away text, djtr_num_tr text,
    new_incident_location text, new_incident_description text,
    new_nar_before_incident text, new_nar_what_happened text,
    new_nar_injury_illness text, new_nar_object_substance text,
    nature_code_pred text, nature_title_pred text, part_code_pred text,
    part_title_pred text, event_code_pred text, event_title_pred text,
    source_code_pred text, source_title_pred text, sec_source_code_pred text,
    sec_source_title_pred text
);

INSERT INTO raw.osha_case_detail VALUES
('1001','E1','Acme Care','111111111','Acme Holdings','1 Main St','Austin','TX','73301','622110','2022','General Medical Hospitals','1','3','500','1000000','C-1','Nurse','29-1141','Registered Nurses','01MAR2024',NULL,'04MAR2025:17:09:00','2024','2','1','5','0','Patient room','Lifting a patient','Moving a patient','Struck by a falling monitor','Bruised arm','Monitor','64','Struck by object','41','Arm','64','Struck by propelled or falling object','71','Monitor','0','None'),
('1002','E1','Acme Care','111111111','Acme Holdings','1 Main St','Austin','TX','73301','622110','2022','General Medical Hospitals','1','3','500','1000000','C-2','Orderly','31-1131','Nursing Assistants','08MAR2024',NULL,'04MAR2025:17:09:00','2024','3','1','0','10','Hallway','Walking to a ward','Carrying supplies','Slipped on a wet floor','Sprained ankle','Floor','43','Sprain','41','Ankle','43','Slip or trip without fall','55','Wet floor','0','None'),
('1003','E2','Globex Freight','222222222','Globex Inc','2 Dock Rd','Fresno','CA','93650','484110','2022','General Freight Trucking','1','22','150','400000','C-3','Driver','53-3032','Truck Drivers','03OCT2024',NULL,'10FEB2025:19:17:00','2024','4','1','0','0','Loading dock','Securing cargo','Pulling a strap','Overexertion while pulling','Back strain','Strap','71','Strain','30','Back','71','Overexertion in pulling','62','Cargo strap','0','None'),
('1004','E2','Globex Freight','222222222','Globex Inc','2 Dock Rd','Fresno','CA','93650','484110','2022','General Freight Trucking','1','22','150','400000','C-4','Loader','53-7062','Laborers','21JUN2024',NULL,'10FEB2025:19:17:00','2024','2','1','20','0','Warehouse','Cleaning equipment','Using a solvent','Exposed to chemical fumes','Respiratory irritation','Solvent','55','Respiratory','62','Lungs','55','Exposure to harmful substances','19','Solvent','0','None'),
('1005','E3','Initech Plant','333333333','Initech LLC','3 Mill Ave','Buffalo','NY','14201','339999','2022','All Other Manufacturing','1','3','800','1600000','C-5','Operator','51-4041','Machinists','30SEP2024','05OCT2024','28FEB2025:15:05:00','2024','1','1','0','0','Shop floor','Operating a press','Reaching into the press','Caught in machinery, fatal','Fatal crush injury','Press','64','Crushing','41','Hand','11','Violent act','71','Press','0','None');

CREATE TABLE raw.llm_enrichment (
    incident_id text PRIMARY KEY,
    contributing_factor text,
    severity_tier text,
    event_category text,
    recurrence_prevention text,
    confidence double precision,
    prompt_version text,
    model_name text,
    enriched_at timestamp
);

INSERT INTO raw.llm_enrichment VALUES
('b8c37e33defde51cf91e1e03e51657da','unsecured equipment','serious','struck_by_or_against','mount monitors with a safety bracket',0.8,'v1','fixture','2025-03-01 12:00:00'),
('fba9d88164f3e2d9109ee770223212a0','wet floor','moderate','fall_slip_trip','add anti-slip matting and wet-floor signage',0.7,'v1','fixture','2025-03-01 12:00:00'),
('aa68c75c4a77c87f97fb686b2f068676','manual pulling force','minor','overexertion_bodily_reaction','provide a powered cargo winch',0.6,'v1','fixture','2025-03-01 12:00:00'),
('fed33392d3a48aa149a87a38b875ba4a','chemical exposure','moderate','other','require local exhaust ventilation and respirators',0.3,'v1','fixture','2025-03-01 12:00:00'),
('2387337ba1e0b0249ba90f55b2ba2521','unguarded press','severe','violence','install a two-hand control and light curtain',0.9,'v1','fixture','2025-03-01 12:00:00');
