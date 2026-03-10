# Category I: Identity & Ownership Intelligence Cubes

## 1. `aircraft_enrichment` — Who Owns This Aircraft?

**Purpose:** Resolve ICAO hex codes and registrations into full aircraft identity profiles by querying multiple open-source databases.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream (extracts hex_list or flight_ids) |
| `hex_list` | LIST_OF_STRINGS | No | ICAO24 hex addresses (Alison provider) |
| `flight_ids` | LIST_OF_STRINGS | No | FR flight IDs (fallback) |
| `registrations` | LIST_OF_STRINGS | No | Tail numbers to look up directly |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `aircraft` | JSON_OBJECT | Array of enriched aircraft profiles |
| `hex_list` | LIST_OF_STRINGS | Passthrough hex addresses |

**Aircraft profile fields:** hex, registration, aircraft_type, manufacturer, model, operator, owner_name, owner_address, country, serial_number (MSN), year_built, engine_type

### Logic
1. For each hex/registration, query **hexdb.io API** (`https://hexdb.io/api/v1/aircraft/{hex}`) for registration, type, operator
2. If registration starts with `N` (US aircraft), look up **FAA N-Number Registry** for owner name, address, certificate details
3. Merge with local `public.aircraft` table for Alison-sourced data (icao_type, last_seen)
4. Deduplicate and return unified profile per aircraft

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **hexdb.io** | REST API | Free | Reasonable use |
| **FAA N-Number Registry** | Bulk CSV download (~60MB, daily refresh) | Free | N/A (local) |
| `public.aircraft` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- FAA registry CSVs should be downloaded and cached locally (daily refresh cron)
- hexdb.io calls should be batched and cached (TTL ~24h)
- Category: **ANALYSIS** (enrichment)

---

## 2. `sanctions_screener` — OFAC/EU/UN Sanctions Check

**Purpose:** Screen aircraft registrations, operators, and owners against global sanctions lists. Automated compliance and intelligence screening in a visual workflow.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream (extracts registrations, operators, owners) |
| `registrations` | LIST_OF_STRINGS | No | Aircraft tail numbers to screen |
| `entity_names` | LIST_OF_STRINGS | No | Operator/owner names to screen |
| `hex_list` | LIST_OF_STRINGS | No | ICAO hex addresses (resolved to registrations first) |
| `search_mode` | STRING | No | `"registration"`, `"entity"`, or `"both"` (default: `"both"`) |
| `min_score` | NUMBER | No | Minimum fuzzy match score 0-100 (default: 80) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `matches` | JSON_OBJECT | Array of sanctions matches with details |
| `flagged_registrations` | LIST_OF_STRINGS | Registrations with sanctions hits |
| `clean_registrations` | LIST_OF_STRINGS | Registrations with no hits |
| `count` | NUMBER | Number of flagged aircraft |

**Match fields:** registration, matched_name, list_source (OFAC SDN, BIS Entity, EU, UN, etc.), match_score, designation_date, program, country, remarks

### Logic
1. Resolve hex addresses to registrations via hexdb.io / local DB if needed
2. For each registration: query **US Consolidated Screening List (CSL) API** with fuzzy matching
3. For each operator/owner name: query CSL API with fuzzy name match
4. Optionally query **OpenSanctions API** for broader coverage (EU, UN, 100+ lists)
5. Aggregate results, deduplicate, sort by match score descending
6. Split output into flagged vs clean lists

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **US CSL API** (`api.trade.gov/consolidated_screening_list`) | REST API | Free (API key required) | Reasonable use |
| **OpenSanctions API** (`api.opensanctions.org`) | REST API | Free (non-commercial) / Paid (commercial) | Documented |
| **OFAC SDN List** | Bulk CSV/XML download | Free | N/A (local) |

### Implementation Notes
- CSL API consolidates 11 US lists (OFAC SDN, BIS Entity, BIS Denied Persons, etc.) — single query covers all
- OFAC SDN list can also be downloaded as bulk CSV for offline/faster screening
- OpenSanctions adds EU, UN, and 100+ other jurisdictions
- Fuzzy matching is critical — sanctioned entities change spellings, use transliterations
- Category: **ANALYSIS**

---

## 3. `ownership_chain_tracker` — Serial Number Persistence

**Purpose:** Track an aircraft through all its registration changes using the immutable manufacturer serial number (MSN). Reveals ownership chains, rapid transfers, and sanctions evasion patterns.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `registration` | STRING | No | Current or historical tail number |
| `serial_number` | STRING | No | Manufacturer serial number (MSN/CSN) |
| `hex` | STRING | No | ICAO24 hex address |

At least one input required.

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `chain` | JSON_OBJECT | Array of ownership records in chronological order |
| `current_registration` | STRING | Current active registration |
| `total_transfers` | NUMBER | Number of ownership changes |
| `rapid_transfer_flag` | BOOLEAN | True if transfers happened faster than 90 days apart |
| `countries` | LIST_OF_STRINGS | All countries the aircraft was registered in |

**Chain record fields:** registration, country, owner_name, operator, start_date, end_date, status, serial_number

### Logic
1. Resolve input to serial number (MSN) via hexdb.io or FAA registry
2. Query **FAA deregistered aircraft database** for historical US registrations with same MSN
3. Query **FR24 `flight_summary`** historical data to find all callsigns/registrations associated with the aircraft
4. Build chronological chain of registrations and operators
5. Flag rapid transfers (< 90 days between ownership changes — classic evasion signal)
6. Flag high-risk jurisdiction changes (e.g., moving from EU to secrecy jurisdictions)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FAA Aircraft Registry** (active + deregistered) | Bulk CSV | Free | N/A |
| **hexdb.io** | REST API | Free | Reasonable use |
| **FR24 API** (`flight_summary`) | REST API | Paid (credits) | Per subscription |

### Implementation Notes
- FAA provides both active and deregistered aircraft databases as separate CSVs
- MSN is the key that ties all registrations together — it never changes
- Category: **ANALYSIS**

---

## 4. `registration_country_risk` — Country Risk Scoring

**Purpose:** Score aircraft by the risk profile of their registration country, using transparency indices, FATF status, and known flag-of-convenience registries.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream |
| `hex_list` | LIST_OF_STRINGS | No | ICAO24 hex addresses |
| `registrations` | LIST_OF_STRINGS | No | Tail numbers |
| `risk_threshold` | NUMBER | No | Minimum risk score to flag (0-100, default: 50) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `scored_aircraft` | JSON_OBJECT | Array of aircraft with risk scores and breakdown |
| `high_risk_ids` | LIST_OF_STRINGS | IDs of aircraft above threshold |
| `count` | NUMBER | Number of high-risk aircraft |
| `risk_summary` | JSON_OBJECT | Aggregated stats by country |

**Score breakdown fields:** registration, country, cpi_score, fatf_status, is_foc (flag of convenience), secrecy_score, composite_risk_score

### Logic
1. Resolve hex/registrations to countries using existing `icao24_lookup.py` ranges + hexdb.io
2. Look up each country against:
   - **Transparency International CPI** (corruption perception index — lower = more corrupt)
   - **FATF grey/black list** membership
   - Known aviation **flag-of-convenience** registries (Aruba, San Marino, Isle of Man, Cayman Islands, Bermuda, etc.)
   - **Tax Justice Network** secrecy index
3. Compute composite risk score (weighted average of factors)
4. Flag aircraft above threshold

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **Transparency International CPI** | Annual CSV/Excel download | Free | N/A |
| **FATF grey/black lists** | Published list (scraped/maintained) | Free | N/A |
| **Flag-of-convenience registries** | Static lookup table | Free | N/A |
| Existing `icao24_lookup.py` | Local module | Free | N/A |

### Implementation Notes
- CPI, FATF, and FoC data changes infrequently — can be bundled as static data files updated annually
- Builds on existing `registration_country_filter` cube's ICAO24 range logic
- Category: **ANALYSIS**
