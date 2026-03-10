# Category III: Geopolitical & Conflict Intelligence Cubes

## 10. `conflict_zone_overlay` — ACLED Event Correlation

**Purpose:** Correlate flight data with armed conflict events from the ACLED database. Annotate flights with proximity to battles, explosions, protests, and other conflict events along their route or at their destination.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs to check |
| `polygon` | JSON_OBJECT | No | Area of interest [[lat, lon], ...] |
| `airport_codes` | LIST_OF_STRINGS | No | ICAO codes to check for nearby conflict |
| `radius_km` | NUMBER | No | Proximity radius for matching (default: 50) |
| `lookback_days` | NUMBER | No | How far back to search for events (default: 30) |
| `event_types` | LIST_OF_STRINGS | No | ACLED event types to include: battles, explosions, violence_against_civilians, protests, riots, strategic_developments (default: all) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `annotated_flights` | JSON_OBJECT | Flights with nearby conflict events attached |
| `conflict_events` | JSON_OBJECT | Array of ACLED events in the area |
| `risk_scores` | JSON_OBJECT | Per-flight or per-airport risk scores |
| `flight_ids` | LIST_OF_STRINGS | Flights with conflict proximity |
| `count` | NUMBER | Number of flights near conflict events |

**Conflict event fields:** event_date, event_type, sub_event_type, actor1, actor2, country, admin1, location, latitude, longitude, fatalities, source, notes

**Risk score fields:** flight_id, destination_risk, route_risk, total_events_nearby, nearest_event_km, fatalities_nearby

### Logic
1. Get flight positions/destinations from local DB or upstream full_result
2. Query **ACLED API** (`https://api.acleddata.com/acled/read`) with:
   - Geographic filter (bounding box around flight route/destination)
   - Time filter (last N days)
   - Event type filter
3. For each flight:
   - Compute distance from destination airport to each conflict event
   - Compute distance from track points to nearby events
   - Aggregate into risk score (weighted by: event severity, proximity, recency)
4. Sort and flag flights with high conflict proximity

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **ACLED API** (`api.acleddata.com`) | REST API | Free with registration (API key + email) | Reasonable use |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.normal_tracks` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- ACLED covers 200+ countries with near-real-time updates
- Cache ACLED responses (TTL ~6 hours) to avoid redundant API calls
- Event types map: Battles, Explosions/Remote violence, Violence against civilians, Protests, Riots, Strategic developments
- Can be used standalone (with polygon input) or chained after flight data cubes
- Category: **ANALYSIS**

---

## 11. `notam_checker` — Active Restrictions & Conflict NOTAMs

**Purpose:** Check for active NOTAMs (Notices to Air Missions) along a flight route or at specific airports. Focuses on security-relevant NOTAMs: airspace closures, GPS interference warnings, temporary flight restrictions, and conflict-related advisories.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airport_codes` | LIST_OF_STRINGS | No | ICAO codes to check |
| `polygon` | JSON_OBJECT | No | Area to search for area NOTAMs [[lat, lon], ...] |
| `flight_ids` | LIST_OF_STRINGS | No | Flights whose routes to check |
| `categories` | LIST_OF_STRINGS | No | NOTAM categories to include: `"closure"`, `"gps_interference"`, `"conflict"`, `"tfr"`, `"military"`, `"all"` (default: `"all"`) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `notams` | JSON_OBJECT | Array of active NOTAMs matching criteria |
| `affected_airports` | LIST_OF_STRINGS | Airport codes with active security NOTAMs |
| `gps_warnings` | JSON_OBJECT | Specific GPS interference NOTAMs (subset) |
| `count` | NUMBER | Total matching NOTAMs |

**NOTAM fields:** notam_id, location (ICAO), type, category, text, effective_start, effective_end, area (lat/lon/radius), altitude_lower, altitude_upper, source

### Logic
1. Resolve inputs to airport codes and/or geographic areas
2. Query **FAA NOTAM API** or **aviationweather.gov** NOTAM endpoint
3. Parse NOTAM text for security-relevant keywords:
   - GPS interference: "GPS", "GNSS", "JAMMING", "INTERFERENCE", "UNRELIABLE"
   - Closures: "CLOSED", "PROHIBITED", "RESTRICTED"
   - Conflict: "HAZARD", "CONFLICT", "MISSILE", "MILITARY OPERATIONS"
   - TFR: "TEMPORARY FLIGHT RESTRICTION"
4. Classify each NOTAM into security categories
5. For flight routes: check if any route segment passes through NOTAM areas

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **aviationweather.gov NOTAM API** | REST API | Free, no key | Reasonable use |
| **FAA NOTAM Search** (`notams.aim.faa.gov`) | Web API | Free | Reasonable use |

### Implementation Notes
- GPS interference NOTAMs are especially valuable — correlate with your `jamming_grid` data
- Middle East and Baltic region GPS NOTAMs have been persistent since 2023
- NOTAM text is semi-structured — keyword extraction + regex parsing required
- Category: **ANALYSIS**

---

## 12. `airspace_closure_detector` — Effective Closure Detection (Behavioral)

**Purpose:** Detect de facto airspace closures by analyzing traffic density drops, even before official NOTAMs are published. Uses actual flight behavior as a real-time indicator of airspace status.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | Yes | Area to monitor [[lat, lon], ...] |
| `analysis_hours` | NUMBER | No | Recent hours to analyze (default: 24) |
| `baseline_days` | NUMBER | No | Days of history for baseline traffic (default: 14) |
| `drop_threshold_pct` | NUMBER | No | Percentage drop to trigger alert (default: 70) |
| `granularity_hours` | NUMBER | No | Time bucket size for density computation (default: 1) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `closures` | JSON_OBJECT | Array of detected closure events |
| `traffic_timeline` | JSON_OBJECT | Hourly flight counts (actual vs baseline) |
| `is_closed` | BOOLEAN | Whether area is currently effectively closed |
| `current_drop_pct` | NUMBER | Current traffic reduction percentage |

**Closure event fields:** start_ts, end_ts, duration_hours, severity (partial/full), baseline_flights_per_hour, actual_flights_per_hour, drop_percentage, affected_airlines (list)

### Logic
1. Query `live.flight_metadata` or `research.flight_metadata` for flights passing through polygon in `baseline_days`
2. Compute baseline traffic density: mean flights per hour through the area (by day-of-week and hour-of-day)
3. Query recent `analysis_hours` of traffic through same area
4. Compare actual vs baseline per time bucket:
   - Drop > `drop_threshold_pct` → flag as effective closure
   - 50-70% drop → partial closure
   - > 90% drop → full closure
5. Identify closure start/end times
6. List affected airlines (who normally flies through but stopped)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `live.normal_tracks` / `research.normal_tracks` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Uses only local DB data — no external API needed
- Day-of-week baseline is important (Friday traffic ≠ Monday traffic)
- The `live.*` schema has real-time data — best for this cube
- Polygon filtering can reuse existing ray-casting or Shapely logic
- Category: **ANALYSIS**

---

## 13. `arms_transfer_tracker` — Military Logistics Monitor

**Purpose:** Track heavy transport and military cargo aircraft movements between known military facilities. Correlate with SIPRI arms transfer data for context. Detect logistics surges that may indicate force buildup or arms transfers.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | No | Geographic area to monitor |
| `airport_codes` | LIST_OF_STRINGS | No | Specific military airfields to monitor |
| `aircraft_types` | LIST_OF_STRINGS | No | ICAO type codes to filter (default: IL76, AN12, AN124, C17, C130, A400, C5) |
| `time_range_days` | NUMBER | No | Lookback period (default: 30) |
| `include_sipri` | BOOLEAN | No | Cross-reference SIPRI data (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `movements` | JSON_OBJECT | Array of military/cargo transport flights |
| `route_network` | JSON_OBJECT | Aggregated routes with frequency and aircraft types |
| `surge_alerts` | JSON_OBJECT | Routes/airports with unusual activity spikes |
| `sipri_context` | JSON_OBJECT | Relevant arms transfer records for involved countries |
| `flight_ids` | LIST_OF_STRINGS | Matching flight IDs |

**Movement fields:** flight_id, callsign, aircraft_type, operator, origin, destination, timestamp, is_military, route_frequency_vs_baseline

### Logic
1. Query `live.flight_metadata` filtered by:
   - `category = 'Military_and_government'` or aircraft type in heavy transport list
   - Time range and geographic area
2. Aggregate into route network (origin-dest pairs with counts)
3. Compare current period activity against historical baseline
4. Flag routes with unusual spikes (> 2 stddev above mean)
5. If `include_sipri`: query **SIPRI Arms Transfers Database** for recent transfers involving origin/destination countries
6. Correlate: military logistics surge + known SIPRI transfer = high-confidence arms movement

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| **SIPRI Arms Transfers** (`armstransfers.sipri.org`) | Web query / CSV | Free | Reasonable use |
| Military airfield database (OurAirports `type=military`) | CSV | Free | N/A |

### Implementation Notes
- `live.flight_metadata` has a `category` field with `Military_and_government` — perfect for this
- Also has `military_type` field for further classification
- Heavy transport aircraft types are distinctive — IL-76, AN-124, C-17 are hard to miss
- SIPRI data provides strategic context but is not real-time (updated periodically)
- Category: **ANALYSIS**
