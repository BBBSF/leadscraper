# BBB Bay Area lead-source configuration
# Start with official data/API sources, then layer in chamber/trade directories.

sources:
  datasf_registered_business_locations:
    enabled: true
    type: socrata
    description: "SF registered business locations / tax registry"
    domain: "data.sfgov.org"
    dataset_id: "g8m3-pdis"
    source_url: "https://data.sfgov.org/Economy-and-Community/Registered-Business-Locations-San-Francisco/g8m3-pdis"
    recency_date_candidates:
      - "location_start_date"
      - "business_start_date"
      - "dba_start_date"
      - "registration_date"
    where_extra: "(business_status IS NULL OR upper(business_status) NOT LIKE '%CLOSED%')"
    limit: 50000
    category: "business_registry"
    notes: "Broad funnel. Best used with days-back recency filtering and high-value category scoring."

  sf_building_permits:
    enabled: true
    type: socrata
    description: "SF building permit applications"
    domain: "data.sfgov.org"
    dataset_id: "i98e-djp9"
    source_url: "https://data.sfgov.org/Housing-and-Buildings/Building-Permits/i98e-djp9"
    recency_date_candidates:
      - "permit_creation_date"
      - "filed_date"
      - "issued_date"
      - "completed_date"
    limit: 50000
    category: "permit"
    notes: "Intent signal. Good for contractors, remodelers, solar, roofing, electrical, plumbing."

  sf_building_permit_contacts:
    enabled: true
    type: socrata
    description: "Contacts associated with SF building permits"
    domain: "data.sfgov.org"
    dataset_id: "3pee-9qhc"
    source_url: "https://data.sfgov.org/Housing-and-Buildings/Building-Permits-Contacts/3pee-9qhc"
    recency_date_candidates:
      - "data_as_of"
      - "permit_creation_date"
      - "filed_date"
    limit: 50000
    category: "permit_contact"
    notes: "Joinable to permits by permit/application number where fields are present."

  berkeley_business_licenses:
    enabled: true
    type: socrata
    description: "City of Berkeley business licenses"
    domain: "data.cityofberkeley.info"
    dataset_id: "rwnf-bu3w"
    source_url: "https://data.cityofberkeley.info/Business/Business-Licenses/rwnf-bu3w"
    recency_date_candidates:
      - "issue_date"
      - "license_start_date"
      - "business_start_date"
      - "application_date"
    limit: 50000
    category: "business_license"

  sf_chamber_directory:
    enabled: true
    type: growthzone_directory
    description: "San Francisco Chamber member directory"
    base_url: "https://business.sfchamber.com/list"
    alpha_url_template: "https://business.sfchamber.com/list/searchalpha/{letter}"
    source_url: "https://business.sfchamber.com/list"
    category: "chamber_member"
    max_pages_per_letter: 5

  oakland_chamber_directory:
    enabled: true
    type: growthzone_directory
    description: "Oakland Metropolitan Chamber member directory"
    base_url: "https://business.oaklandchamber.com/list"
    alpha_url_template: "https://business.oaklandchamber.com/list/searchalpha/{letter}"
    source_url: "https://business.oaklandchamber.com/list"
    category: "chamber_member"
    max_pages_per_letter: 5

  marin_builders_directory:
    enabled: true
    type: growthzone_directory
    description: "Marin Builders Association member directory"
    base_url: "https://members.marinbuilders.com/list"
    alpha_url_template: "https://members.marinbuilders.com/list/searchalpha/{letter}"
    source_url: "https://members.marinbuilders.com/list"
    category: "trade_association_member"
    max_pages_per_letter: 5

  cslb_manual_ingest:
    enabled: true
    type: local_file_ingest
    description: "CSLB contractor list downloaded from public data portal"
    source_url: "https://www.cslb.ca.gov/onlineservices/dataportal/ListByCounty"
    input_glob: "data/manual_inputs/cslb*.csv"
    category: "licensed_contractor"
    notes: "Download CSLB CSV/XLS from the public data portal, save as data/manual_inputs/cslb_YYYYMMDD.csv, then run this source."

lead_scoring:
  high_value_keywords:
    - "contractor"
    - "construction"
    - "roof"
    - "roofing"
    - "solar"
    - "hvac"
    - "heating"
    - "air conditioning"
    - "plumbing"
    - "electrical"
    - "electrician"
    - "remodel"
    - "restoration"
    - "mold"
    - "water damage"
    - "moving"
    - "mover"
    - "auto repair"
    - "smog"
    - "tree service"
    - "landscaping"
    - "pool"
    - "window"
    - "flooring"
    - "security"
    - "locksmith"
    - "home improvement"
  bay_area_cities:
    - "san francisco"
    - "oakland"
    - "berkeley"
    - "san rafael"
    - "sausalito"
    - "alameda"
    - "san leandro"
    - "hayward"
    - "fremont"
    - "richmond"
    - "walnut creek"
    - "concord"
    - "daly city"
    - "south san francisco"
    - "redwood city"
    - "san mateo"
    - "san jose"
    - "santa rosa"
    - "novato"
    - "mill valley"
    - "larkspur"
    - "petaluma"
