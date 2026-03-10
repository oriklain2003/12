# Category VII: Reference & Enrichment Cubes

## 20. `airport_enrichment` — Rich Airport Context

**Purpose:** Enrich ICAO/IATA airport codes with comprehensive context: location, elevation, type (military/private/commercial), country, municipality, runway details, and frequencies. Makes every airport code in a workflow human-readable.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airport_codes` | LIST_OF_STRINGS | No | ICAO or IATA codes to look up |
| `full_result` | JSON_OBJECT | No | Accepts full result — extracts origin/destination airports |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs (resolved to airports via metadata) |
| `country_filter` | LIST_OF_STRINGS | No | ISO country codes to filter results |
| `type_filter` | LIST_OF_STRINGS | No | Airport types: `"large_airport"`, `"medium_airport"`, `"small_airport"`, `"heliport"`, `"military"`, `"closed"` |
| `polygon` | JSON_OBJECT | No | Find all airports within polygon |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `airports` | JSON_OBJECT | Array of enriched airport records |
| `airport_codes` | LIST_OF_STRINGS | Resolved ICAO codes |
| `map_data` | JSON_OBJECT | GeoJSON FeatureCollection of airport locations |
| `count` | NUMBER | Number of airports returned |

**Airport record fields:** icao_code, iata_code, name, type (large/medium/small/heliport/military/closed), latitude, longitude, elevation_ft, country_code, country_name, region, municipality, has_scheduled_service, runways (array of {length_ft, width_ft, surface, lighted, closed}), frequencies (array of {type, description, mhz})

### Logic
1. Resolve inputs to airport codes:
   - Direct from `airport_codes`
   - From `full_result` (extract origin_airport, destination_airport fields)
   - From `flight_ids` via flight_metadata lookup
   - From `polygon` via spatial query on airport coordinates
2. Look up each code in **OurAirports** database:
   - Main airport record from `airports.csv`
   - Runways from `runways.csv` (joined by airport_ref)
   - Frequencies from `airport-frequencies.csv` (joined by airport_ref)
3. Classify military airports (type = "military" or keywords in name)
4. Generate GeoJSON points for map rendering

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **OurAirports** (`ourairports.com/data/`) | CSV download (daily refresh) | Free, public domain | N/A (local) |

**OurAirports files used:**
- `airports.csv` — 78,000+ airports with coordinates, type, country
- `runways.csv` — runway details per airport
- `airport-frequencies.csv` — radio frequencies per airport
- `countries.csv` — country reference data
- `regions.csv` — subdivision reference data

### Implementation Notes
- Download and cache OurAirports CSVs locally (refresh weekly/daily cron)
- Load into pandas DataFrames or SQLite at startup for fast lookups
- Airport type classification is crucial for other cubes (meeting_detector scores by airport size)
- The polygon search mode enables "find all airports in this area" workflows
- Category: **DATA_SOURCE** (reference)

---

## 21. `airspace_lookup` — Airspace Boundaries & Restrictions

**Purpose:** Determine which airspaces a flight traversed or check if specific coordinates fall within restricted/prohibited/danger areas. Essential for route legality analysis and understanding flight context.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs — check which airspaces they crossed |
| `point` | JSON_OBJECT | No | Single point {lat, lon} to check |
| `polygon` | JSON_OBJECT | No | Area to find all airspaces within |
| `airspace_classes` | LIST_OF_STRINGS | No | Filter by class: `"FIR"`, `"TMA"`, `"CTR"`, `"restricted"`, `"prohibited"`, `"danger"`, `"MOA"`, `"all"` (default: `"all"`) |
| `altitude_ft` | NUMBER | No | Filter airspaces active at this altitude |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `airspaces` | JSON_OBJECT | Array of matching airspace records |
| `intersected_airspaces` | JSON_OBJECT | Per-flight list of airspaces crossed (if flight_ids provided) |
| `restricted_areas` | JSON_OBJECT | Subset: only restricted/prohibited/danger areas |
| `boundaries` | JSON_OBJECT | GeoJSON FeatureCollection of airspace polygons |
| `count` | NUMBER | Number of matching airspaces |

**Airspace record fields:** id, name, class (FIR/TMA/CTR/restricted/prohibited/danger/MOA), country, lower_limit_ft, upper_limit_ft, active_times, geometry (GeoJSON Polygon), source

### Logic
1. Load airspace boundary data from **OpenAIP** or pre-downloaded GeoJSON files
2. If `flight_ids` provided:
   - Get flight tracks from local DB
   - For each track point: check point-in-polygon against airspace boundaries
   - Build list of airspaces traversed with entry/exit timestamps
3. If `point` or `polygon` provided:
   - Spatial query for airspaces intersecting the area
4. Filter by airspace class and altitude
5. Generate GeoJSON for visualization

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **OpenAIP** (`openaip.net`) | API/Download | Free (non-commercial) | Documented |
| **Eurocontrol Atlas** (European FIR/UIR) | Shapefile on GitHub | Free | N/A |
| **FAA Open Data** (US airspace) | GeoJSON via ArcGIS | Free | N/A |

### Implementation Notes
- Airspace boundaries should be pre-downloaded and stored as GeoJSON files (updated monthly)
- Use Shapely/GeoPandas for spatial intersection operations
- Restricted/prohibited areas are the most intelligence-relevant subset
- FIR boundaries are essential for understanding jurisdiction crossings
- The `crossed_borders` field in `live.flight_metadata` provides some of this, but this cube gives full detail
- Category: **ANALYSIS** (enrichment)

---

## 22. `fr24_airport_activity` — FR24 Airport Traffic Snapshot

**Purpose:** Get a comprehensive activity snapshot for any airport using the FR24 API. Shows all arrivals/departures classified by category, airline, and aircraft type. Enables military base monitoring, private airfield surveillance, and traffic pattern analysis.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airport_code` | STRING | Yes | ICAO or IATA airport code |
| `time_range_days` | NUMBER | No | Lookback period (default: 7) |
| `category_filter` | LIST_OF_STRINGS | No | Aircraft categories: `"Passenger"`, `"Cargo"`, `"Military_and_government"`, `"Business_jets"`, `"General_aviation"`, `"Other_service"` |
| `direction` | STRING | No | `"arrivals"`, `"departures"`, `"both"` (default: `"both"`) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `flights` | JSON_OBJECT | Array of flight records at this airport |
| `flight_ids` | LIST_OF_STRINGS | Flight IDs for downstream processing |
| `activity_stats` | JSON_OBJECT | Aggregated stats by category, airline, aircraft type, hour-of-day |
| `timeline` | JSON_OBJECT | Hourly activity counts for visualization |
| `count` | NUMBER | Total flights |

**Flight record fields:** flight_id, callsign, registration, aircraft_type, airline, category, origin (if arrival), destination (if departure), scheduled_time, actual_time, direction (arr/dep)

**Activity stats fields:** by_category (dict of category → count), by_airline (dict), by_aircraft_type (dict), by_hour (array of 24 counts), avg_daily_movements, peak_hour, nighttime_ratio

### Logic
1. Query **FR24 API `flight_summary`** filtered by airport code and date range
2. Separate into arrivals and departures
3. Classify each flight by category (using live.flight_metadata categories or FR24 data)
4. Compute activity statistics:
   - Movements per category
   - Hourly distribution (detect nighttime operations)
   - Unique airlines and aircraft types
   - Average daily movement count
5. Build timeline for visualization

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`flight_summary`) | REST API | Paid (credits) | Per subscription |
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Can fall back to local DB (`live.flight_metadata` filtering by origin/destination) when FR24 credits are limited
- `live.flight_metadata` has the `category` field — may be sufficient without FR24 for monitored airspace
- Nighttime ratio is a key indicator for military/covert operations
- Heavy transport presence at normally quiet airports is a high-value signal
- Category: **DATA_SOURCE**
