{#
  Reusable mapping macros for the mart layer:
  - naics_sector:           2-digit NAICS prefix to sector name
  - census_region:          US state to census region
  - coarse_event_from_llm:  LLM EventCategory enum to a coarse event bucket
  - coarse_event_from_oiics: OIICS event code (leading division digit) to the
                            same coarse bucket, so the two are comparable
  The coarse buckets collapse the LLM's struck_by_or_against and
  contact_with_equipment into one "contact_or_struck" bucket, because OIICS
  division 6 (Contact with objects and equipment) does not distinguish them.
#}

{% macro naics_sector(naics_code) -%}
case left({{ naics_code }}, 2)
    when '11' then 'Agriculture, Forestry, Fishing and Hunting'
    when '21' then 'Mining, Quarrying, and Oil and Gas Extraction'
    when '22' then 'Utilities'
    when '23' then 'Construction'
    when '31' then 'Manufacturing'
    when '32' then 'Manufacturing'
    when '33' then 'Manufacturing'
    when '42' then 'Wholesale Trade'
    when '44' then 'Retail Trade'
    when '45' then 'Retail Trade'
    when '48' then 'Transportation and Warehousing'
    when '49' then 'Transportation and Warehousing'
    when '51' then 'Information'
    when '52' then 'Finance and Insurance'
    when '53' then 'Real Estate and Rental and Leasing'
    when '54' then 'Professional, Scientific, and Technical Services'
    when '55' then 'Management of Companies and Enterprises'
    when '56' then 'Administrative, Support, and Waste Management Services'
    when '61' then 'Educational Services'
    when '62' then 'Health Care and Social Assistance'
    when '71' then 'Arts, Entertainment, and Recreation'
    when '72' then 'Accommodation and Food Services'
    when '81' then 'Other Services (except Public Administration)'
    when '92' then 'Public Administration'
    else 'Unknown'
end
{%- endmacro %}

{% macro census_region(state) -%}
case upper({{ state }})
    when 'CT' then 'Northeast'
    when 'ME' then 'Northeast'
    when 'MA' then 'Northeast'
    when 'NH' then 'Northeast'
    when 'RI' then 'Northeast'
    when 'VT' then 'Northeast'
    when 'NJ' then 'Northeast'
    when 'NY' then 'Northeast'
    when 'PA' then 'Northeast'
    when 'IL' then 'Midwest'
    when 'IN' then 'Midwest'
    when 'MI' then 'Midwest'
    when 'OH' then 'Midwest'
    when 'WI' then 'Midwest'
    when 'IA' then 'Midwest'
    when 'KS' then 'Midwest'
    when 'MN' then 'Midwest'
    when 'MO' then 'Midwest'
    when 'NE' then 'Midwest'
    when 'ND' then 'Midwest'
    when 'SD' then 'Midwest'
    when 'DE' then 'South'
    when 'FL' then 'South'
    when 'GA' then 'South'
    when 'MD' then 'South'
    when 'NC' then 'South'
    when 'SC' then 'South'
    when 'VA' then 'South'
    when 'DC' then 'South'
    when 'WV' then 'South'
    when 'AL' then 'South'
    when 'KY' then 'South'
    when 'MS' then 'South'
    when 'TN' then 'South'
    when 'AR' then 'South'
    when 'LA' then 'South'
    when 'OK' then 'South'
    when 'TX' then 'South'
    when 'AZ' then 'West'
    when 'CO' then 'West'
    when 'ID' then 'West'
    when 'MT' then 'West'
    when 'NV' then 'West'
    when 'NM' then 'West'
    when 'UT' then 'West'
    when 'WY' then 'West'
    when 'AK' then 'West'
    when 'CA' then 'West'
    when 'HI' then 'West'
    when 'OR' then 'West'
    when 'WA' then 'West'
    else 'Other'
end
{%- endmacro %}

{% macro coarse_event_from_llm(column_name) -%}
case {{ column_name }}
    when 'struck_by_or_against' then 'contact_or_struck'
    when 'contact_with_equipment' then 'contact_or_struck'
    when 'fall_slip_trip' then 'fall_slip_trip'
    when 'overexertion_bodily_reaction' then 'overexertion'
    when 'exposure_harmful_substance' then 'exposure'
    when 'transportation' then 'transportation'
    when 'fire_explosion' then 'fire_explosion'
    when 'violence' then 'violence'
    else 'other'
end
{%- endmacro %}

{% macro coarse_event_from_oiics(column_name) -%}
case
    when {{ column_name }} is null then null
    else
        case left(cast({{ column_name }} as varchar), 1)
            when '1' then 'violence'
            when '2' then 'transportation'
            when '3' then 'fire_explosion'
            when '4' then 'fall_slip_trip'
            when '5' then 'exposure'
            when '6' then 'contact_or_struck'
            when '7' then 'overexertion'
            else 'other'
        end
end
{%- endmacro %}
