# Category II: Behavioral Analysis Cubes (FR24-powered)

## 5. `pattern_of_life` — Behavioral Baseline & Anomaly Detection

**Purpose:** Build a statistical behavioral profile for an aircraft or callsign over time, then score each flight against that baseline to detect deviations. The core intelligence analysis cube.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `registration` | STRING | No | Aircraft registration to profile |
| `callsign` | STRING | No | Callsign pattern (supports wildcards) |
| `hex` | STRING | No | ICAO24 hex address |
| `baseline_days` | NUMBER | No | Days of history for baseline (default: 90) |
| `analysis_days` | NUMBER | No | Recent days to score against baseline (default: 7) |
| `sensitivity` | NUMBER | No | Standard deviations for anomaly threshold (default: 2.0) |

At least one of registration/callsign/hex required.

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `baseline` | JSON_OBJECT | Statistical profile (route frequencies, schedule distribution, dwell times) |
| `anomalous_flights` | JSON_OBJECT | Array of flights exceeding sensitivity threshold with deviation scores |
| `flight_ids` | LIST_OF_STRINGS | IDs of anomalous flights |
| `count` | NUMBER | Number of anomalous flights |
| `pattern_summary` | JSON_OBJECT | Top routes, avg flights/week, typical schedule |

**Baseline fields:** route_distribution (origin-dest pairs with frequency), departure_time_distribution (mean, stddev per route), dwell_time_by_airport, flights_per_week (mean, stddev), typical_altitude_profile

**Anomaly fields:** flight_id, date, route, deviation_type (new_route, off_schedule, unusual_dwell, frequency_spike), deviation_score, details

### Logic
1. Query **FR24 `flight_summary`** for all flights by this aircraft in `baseline_days` window
2. Build statistical profile:
   - Route frequency distribution (which origin-destination pairs, how often)
   - Departure time distribution per route (mean ± stddev)
   - Dwell time at each airport (time between arrival and next departure)
   - Weekly flight count distribution
3. Query recent `analysis_days` flights
4. Score each recent flight against baseline:
   - **New route**: destination never seen in baseline → high score
   - **Off schedule**: departure time > N stddev from route mean → medium score
   - **Unusual dwell**: time at airport > N stddev from airport mean → medium score
   - **Frequency spike**: weekly count > N stddev above mean → medium score
5. Return scored flights sorted by deviation score

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`flight_summary`) | REST API | Paid (credits) | Per subscription |
| `research.flight_metadata` / `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Can use local DB as primary source and FR24 as fallback/supplement for longer history
- FR24 historical data goes back to May 2016 — deep baselines possible
- Cache baseline computations (recompute daily, not per-request)
- Category: **ANALYSIS**

---

## 6. `dark_flight_detector` — Transponder Gap Analysis

**Purpose:** Detect suspicious gaps in ADS-B coverage that cannot be explained by receiver limitations alone. Distinguishes intentional transponder disabling from natural coverage holes.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream |
| `flight_ids` | LIST_OF_STRINGS | No | FR flight IDs |
| `hex_list` | LIST_OF_STRINGS | No | ICAO24 hex addresses |
| `provider` | STRING | No | `"fr"` or `"alison"` (default: `"fr"`) |
| `min_gap_minutes` | NUMBER | No | Minimum gap duration to flag (default: 15) |
| `coverage_threshold` | NUMBER | No | Min coverage score to consider area "covered" (default: 0.5) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `gaps` | JSON_OBJECT | Array of detected gap events |
| `flight_ids` | LIST_OF_STRINGS | Flight IDs with suspicious gaps |
| `count` | NUMBER | Number of gap events |

**Gap event fields:** flight_id, gap_start_ts, gap_end_ts, gap_duration_minutes, last_known_lat, last_known_lon, reacquired_lat, reacquired_lon, straight_line_distance_nm, expected_coverage (from coverage_grid), suspicion_score, nearest_sanctioned_territory, gap_geometry (GeoJSON LineString from last to first reacquired position)

### Logic
1. Get flight tracks from local DB (`research.normal_tracks` or `public.positions`)
2. Sort track points by timestamp, compute inter-point time deltas
3. Identify gaps exceeding `min_gap_minutes`
4. For each gap:
   - Look up `public.coverage_grid` cells along the interpolated path
   - If coverage is good (high `composite_score`, not `is_coverage_hole`) → suspicious
   - If coverage is poor → likely natural gap, low suspicion
   - Compute straight-line distance vs expected flight distance (detect possible intermediate stops)
   - Check proximity to sanctioned territories (Iran, Syria, DPRK, etc.)
5. Score suspicion: high coverage + long gap + near sanctioned territory = high score

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.normal_tracks` / `public.positions` (local DB) | PostgreSQL | Free | N/A |
| `public.coverage_grid` (local DB) | PostgreSQL | Free | N/A |
| Sanctioned territory boundaries | Static GeoJSON | Free | N/A |

### Implementation Notes
- Leverages your existing coverage_grid data (7,769 cells) — currently unused!
- Sanctioned territory polygons can be a static file derived from OFAC country list
- The gap between "last seen" and "first reacquired" positions is the key analytical unit
- Category: **ANALYSIS**

---

## 7. `holding_pattern_detector` — Orbital Flight Detection

**Purpose:** Detect and classify circular/racetrack flight patterns in track data. Identifies standard holds, surveillance orbits, and search patterns.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream (extracts tracks) |
| `flight_ids` | LIST_OF_STRINGS | No | FR flight IDs to analyze |
| `hex_list` | LIST_OF_STRINGS | No | ICAO hex addresses |
| `provider` | STRING | No | `"fr"` or `"alison"` (default: `"fr"`) |
| `min_orbits` | NUMBER | No | Minimum complete orbits to detect (default: 1.5) |
| `max_radius_nm` | NUMBER | No | Maximum orbit radius in nautical miles (default: 15) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `patterns` | JSON_OBJECT | Array of detected holding/orbit events |
| `flight_ids` | LIST_OF_STRINGS | Flight IDs with detected patterns |
| `count` | NUMBER | Number of pattern events |

**Pattern event fields:** flight_id, classification (holding, surveillance_orbit, search_pattern, racetrack), center_lat, center_lon, radius_nm, orbit_count, start_ts, end_ts, duration_minutes, altitude_ft, direction (CW/CCW), nearest_airport, geometry (GeoJSON of the actual orbital path)

### Logic
1. Get track points for each flight from local DB
2. Compute cumulative heading change over sliding windows
3. Detect segments where cumulative heading change exceeds 360° × `min_orbits`
4. For each detected segment:
   - Compute center of rotation (centroid of track points in segment)
   - Compute mean radius from center
   - Count complete orbits (cumulative heading / 360°)
   - Classify:
     - **Holding**: near airport (< 10 NM from known airport), standard altitude
     - **Surveillance orbit**: persistent (> 30 min), away from airports
     - **Search pattern**: expanding radius or systematic grid pattern
     - **Racetrack**: elongated oval pattern (standard holding shape)
5. Generate GeoJSON for each detected pattern

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.normal_tracks` / `public.positions` (local DB) | PostgreSQL | Free | N/A |
| Airport reference data (OurAirports or local) | CSV/Static | Free | N/A |

### Implementation Notes
- Heading change accumulation is the core algorithm — simple but effective
- Use the `track` column from normal_tracks for heading (already available)
- Airport proximity check can use existing airport data or OurAirports CSV
- Category: **ANALYSIS**

---

## 8. `meeting_detector` — Aircraft Co-location Analysis

**Purpose:** Detect temporal-spatial coincidences between aircraft — two or more aircraft at the same airport/location within a configurable time window. Reveals meetings, coordination, and relationships.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `aircraft_group_a` | LIST_OF_STRINGS | Yes | First group of registrations/hex addresses |
| `aircraft_group_b` | LIST_OF_STRINGS | No | Second group (if empty, checks within group A) |
| `time_window_hours` | NUMBER | No | Max time between arrivals to count as co-located (default: 6) |
| `location_radius_nm` | NUMBER | No | Max distance between positions to count as same location (default: 5) |
| `lookback_days` | NUMBER | No | Historical period to search (default: 90) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `meetings` | JSON_OBJECT | Array of co-location events |
| `pair_count` | NUMBER | Number of unique aircraft pairs with meetings |
| `total_events` | NUMBER | Total meeting events |
| `network` | JSON_OBJECT | Graph data: nodes (aircraft) + edges (meetings) for visualization |

**Meeting event fields:** aircraft_a (reg/hex), aircraft_b (reg/hex), location (airport ICAO or lat/lon), meeting_start, meeting_end, overlap_hours, airport_type (military/private/commercial), meeting_score (rarity-weighted)

### Logic
1. For each aircraft, query **FR24 `flight_summary`** or local DB for all flights in lookback period
2. Extract arrival/departure events at each airport
3. For each pair of aircraft from different groups:
   - Find airports where both aircraft were present
   - Check if arrival times overlap within `time_window_hours`
   - Compute overlap duration
4. Score meetings by rarity:
   - Meeting at a major hub (JFK, LHR) = low score (coincidental)
   - Meeting at a small private airfield = high score (likely intentional)
   - Repeated meetings at different locations = very high score
5. Build network graph of relationships

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`flight_summary`) | REST API | Paid (credits) | Per subscription |
| `research.flight_metadata` / `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Airport classification data (OurAirports) | CSV | Free | N/A |

### Implementation Notes
- Airport size/type is key for scoring — meetings at small airports are far more significant
- The network output enables downstream `network_graph_builder` visualization
- Can operate on local DB data alone (without FR24) for recent history
- Category: **ANALYSIS**

---

## 9. `route_deviation_analyzer` — Off-Expected-Route Detection

**Purpose:** Compare actual flight tracks against expected corridors from learned paths/tubes. Detect and quantify lateral deviations from established routes.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream (extracts flight_ids + tracks) |
| `flight_ids` | LIST_OF_STRINGS | Yes | Flight IDs to analyze |
| `deviation_threshold_nm` | NUMBER | No | Minimum lateral deviation to flag (default: 5.0) |
| `use_tubes` | BOOLEAN | No | Use learned_tubes for reference (default: true) |
| `use_paths` | BOOLEAN | No | Use learned_paths for reference (default: true) |
| `use_sids_stars` | BOOLEAN | No | Use learned SIDs/STARs for departure/arrival phases (default: false) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `deviations` | JSON_OBJECT | Array of deviation events per flight |
| `flight_ids` | LIST_OF_STRINGS | Flight IDs with deviations above threshold |
| `count` | NUMBER | Number of flights with significant deviations |

**Deviation event fields:** flight_id, reference_route_id (tube/path ID), max_deviation_nm, avg_deviation_nm, deviation_start_ts, deviation_end_ts, deviation_segment (GeoJSON LineString), reference_segment (GeoJSON LineString), severity (low/medium/high)

### Logic
1. Get flight tracks from local DB (`research.normal_tracks`)
2. Match each flight to its expected route:
   - Use origin/destination from `flight_metadata` to find matching `learned_tubes` or `learned_paths`
   - If using SIDs/STARs, match departure airport to `learned_sids`, arrival to `learned_stars`
3. For each matched flight-route pair:
   - Compute lateral distance from each track point to nearest point on reference centerline
   - Use Shapely `distance()` with proper geographic projection
   - Identify contiguous segments where deviation exceeds threshold
4. Classify severity:
   - Low: 5-10 NM deviation (weather avoidance typical)
   - Medium: 10-25 NM (ATC reroute or intentional)
   - High: > 25 NM (significant deviation)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.normal_tracks` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `public.learned_tubes` (local DB, 3,145 records) | PostgreSQL | Free | N/A |
| `public.learned_paths` (local DB) | PostgreSQL | Free | N/A |
| `public.learned_sids` (local DB, 189 records) | PostgreSQL | Free | N/A |
| `public.learned_stars` (local DB, 88 records) | PostgreSQL | Free | N/A |

### Implementation Notes
- Leverages existing DB data — learned_tubes (3,145), learned_sids (189), learned_stars (88) are all sitting unused
- Shapely provides the geometric distance computation
- Geographic distance: at cruise altitude, 1° ≈ 60 NM
- Can chain after `get_flight_course` cube (lines mode) for tracks
- Category: **ANALYSIS**
