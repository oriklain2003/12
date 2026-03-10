# Category X: Middle East Intelligence Cubes

Cubes designed specifically for the Levant/Gulf theater, leveraging the DB's heavy ME coverage:
- **Top airports**: LLBG, HECA, OJAI, OLBA, OEJN, OMDB, OERK, OSDI, OKKK, ORBI
- **Anomaly regions**: Egypt (36K), Israel (34K), Cyprus (9K), Jordan (8K), Lebanon (6K), Syria (1K)
- **Active jamming**: Gaza corridor (31.5°N/34.0-34.5°E), Jordan Valley, Negev, Gulf (Hormuz/UAE), Sinai, Lebanon coast
- **Crossed borders**: Israel↔Jordan↔Syria↔Lebanon↔Egypt corridors fully tracked
- **Military presence**: Jordanian C-130s, Russian IL-96, German A400M/A321, US-pattern callsigns (POKER45, COBRA66)

---

## 33. `iran_axis_monitor` — Tehran-Damascus-Beirut Corridor Tracker

**Purpose:** Monitor the Iran→Iraq→Syria→Lebanon arms supply corridor. Track heavy transport flights along this axis, detect new operators, flag sanctioned aircraft, and identify logistics surges. This is the single highest-value intelligence corridor in the Middle East.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `time_range_days` | NUMBER | No | Lookback period (default: 30) |
| `include_iranian_airports` | BOOLEAN | No | Include OIIE (IKA), OIII (Mehrabad), OIFM (Isfahan), OISS (Shiraz) (default: true) |
| `include_syrian_airports` | BOOLEAN | No | Include OSDI (Damascus), OSLK (Latakia/Khmeimim), OSAP (Aleppo) (default: true) |
| `include_lebanese_airports` | BOOLEAN | No | Include OLBA (Beirut) (default: true) |
| `include_iraqi_transit` | BOOLEAN | No | Include ORBI (Baghdad), ORBS (Basra), ORER (Erbil) as transit points (default: true) |
| `aircraft_type_filter` | LIST_OF_STRINGS | No | Focus on heavy transport: IL76, AN12, B744, B748, A306, A30B (default: all) |
| `flag_sanctioned` | BOOLEAN | No | Cross-reference with known sanctioned operator list (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `corridor_flights` | JSON_OBJECT | Flights along the axis with enrichment |
| `flight_ids` | LIST_OF_STRINGS | Matching flight IDs |
| `route_matrix` | JSON_OBJECT | Origin→destination frequency matrix |
| `operator_breakdown` | JSON_OBJECT | Flights grouped by airline/operator |
| `surge_alerts` | JSON_OBJECT | Routes with above-baseline activity |
| `sanctioned_hits` | JSON_OBJECT | Flights by known sanctioned operators |
| `timeline` | JSON_OBJECT | Daily flight counts for trend analysis |
| `count` | NUMBER | Total corridor flights |

**Corridor flight fields:** flight_id, callsign, airline, aircraft_type, origin, destination, timestamp, crossed_borders, is_sanctioned_operator, is_heavy_transport, route_segment (e.g., "Iran→Iraq", "Iraq→Syria", "Syria→Lebanon")

### Logic
1. Define corridor airport sets:
   - **Iran**: OIIE, OIII, OIFM, OISS, OIMM, OIKB
   - **Iraq transit**: ORBI, ORBS, ORER, ORMM, ORNI
   - **Syria**: OSDI, OSLK, OSAP
   - **Lebanon**: OLBA
2. Query `research.flight_metadata` + `live.flight_metadata` for flights where:
   - Origin in one set AND destination in another set (any direction)
   - Time range filter
3. Classify each flight by route segment:
   - Iran→Iraq, Iraq→Syria, Syria→Lebanon (supply direction)
   - Reverse flows (return legs)
   - Full corridor (Iran→Syria/Lebanon with Iraq transit)
4. Build operator breakdown — flag unknown/new operators
5. Cross-reference against **known sanctioned operators list** (static):
   - Mahan Air (W5/IRM), Pouya Air, Qeshm Fars Air (QFZ), Meraj Airlines (MRJ)
   - Caspian Airlines (CPN), Yas Air, IRGC-linked shell operators
   - Syrian Air (RB/SYR), Cham Wings (SAW)
6. Compare current activity vs historical baseline per route segment
7. Flag surges (> 2 stddev above 30-day rolling mean)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Sanctioned operators list | Static JSON (built-in) | Free | N/A |

### Implementation Notes
- The corridor is well-documented by INSS, UN Panel of Experts, and open-source investigators
- Key signal: IL-76, AN-12, Boeing 747F flights on this axis are almost always military cargo
- Iraq is the critical transit point — Iranian flights typically overfly Iraqi airspace en route to Syria
- `crossed_borders` field in `live.flight_metadata` helps identify corridor flights
- Category: **ANALYSIS**

---

## 34. `me_jamming_dashboard` — Middle East GPS Interference Monitor

**Purpose:** Focused GPS jamming/spoofing analysis for the ME theater. Your jamming_grid shows 100% jamming cells around Gaza, Jordan Valley, Negev, Strait of Hormuz, and Sinai. This cube organizes that data into named zones with operational context.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `time_range_hours` | NUMBER | No | Recent hours (default: 24) |
| `zone` | STRING | No | Predefined zone: `"gaza"`, `"negev"`, `"jordan_valley"`, `"lebanon_coast"`, `"hormuz"`, `"sinai"`, `"all"` (default: `"all"`) |
| `min_jamming_pct` | NUMBER | No | Minimum jamming percentage (default: 10) |
| `include_affected_flights` | BOOLEAN | No | List flights affected by jamming in each zone (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `zones` | JSON_OBJECT | Named zones with current jamming status |
| `affected_flights` | JSON_OBJECT | Flights traversing active jamming areas |
| `flight_ids` | LIST_OF_STRINGS | Affected flight IDs |
| `heatmap_data` | JSON_OBJECT | GeoJSON for map overlay |
| `zone_comparison` | JSON_OBJECT | Current vs historical intensity per zone |
| `total_affected_aircraft` | NUMBER | Unique aircraft in jamming zones |

**Zone record fields:** zone_name, zone_polygon (GeoJSON), current_jamming_pct, baseline_jamming_pct, trend (increasing/decreasing/stable), affected_aircraft_count, degraded_reports, first_detected, peak_intensity_time

### Logic
1. Define named ME jamming zones (static polygons):
   - **Gaza corridor**: lat 31.0-32.0, lon 33.5-34.5
   - **Negev/South Israel**: lat 29.5-31.0, lon 34.0-35.0
   - **Jordan Valley**: lat 31.0-33.0, lon 35.5-37.0
   - **Lebanon coast**: lat 33.0-34.5, lon 34.0-36.0
   - **Strait of Hormuz**: lat 24.5-27.0, lon 54.0-57.0
   - **Sinai**: lat 27.0-31.0, lon 31.0-34.0
   - **North Syria**: lat 35.0-37.0, lon 36.0-42.0
   - **Eastern Med**: lat 33.0-36.0, lon 33.0-36.0
2. Query `public.jamming_grid` for cells within each zone + time range
3. Compute per-zone metrics: avg jamming %, peak %, affected aircraft
4. Compare against 7-day rolling baseline for trend detection
5. If `include_affected_flights`:
   - Query `public.anomaly_events` WHERE region='middle_east' for jamming/spoofing events
   - Match affected aircraft hex codes
   - Query `live.flight_metadata` for flight context (airline, route)
6. Generate GeoJSON heatmap for visualization

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `public.jamming_grid` (local DB, 66K+ cells) | PostgreSQL | Free | N/A |
| `public.anomaly_events` (local DB) | PostgreSQL | Free | N/A |
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Your jamming_grid shows 100% jamming at multiple ME cells — this is real, active data
- Gaza corridor (31.5°N/34.0-34.5°E) has 206 + 174 degraded reports with 9+ unique aircraft — significant
- Strait of Hormuz area (25°N/55°E) has 473 degraded reports — Iranian jamming
- Named zones make raw grid data operationally meaningful
- Widget hint: `"heatmap"` with zone boundary overlays
- Category: **ANALYSIS**

---

## 35. `military_callsign_decoder` — Military/Government Flight Identifier

**Purpose:** Identify and classify military/government flights in the ME using callsign patterns, known aircraft types, and registration databases. Your live data shows HERC30, POKER45, COBRA66, GAF901, KAF3210, UAF820 — all decodable military callsigns.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs to classify |
| `hex_list` | LIST_OF_STRINGS | No | ICAO hex addresses |
| `polygon` | JSON_OBJECT | No | Area to scan for military flights |
| `time_range_days` | NUMBER | No | Lookback period (default: 7) |
| `countries_of_interest` | LIST_OF_STRINGS | No | Filter by military nationality: `"US"`, `"IL"`, `"RU"`, `"DE"`, `"UK"`, `"JO"`, `"EG"`, `"SA"`, `"IR"` (default: all) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `military_flights` | JSON_OBJECT | Classified military flight records |
| `flight_ids` | LIST_OF_STRINGS | Military flight IDs |
| `by_nationality` | JSON_OBJECT | Flights grouped by identified nationality |
| `by_role` | JSON_OBJECT | Flights grouped by role (transport, ISR, tanker, VIP, trainer) |
| `count` | NUMBER | Total military flights identified |
| `unidentified` | JSON_OBJECT | Flights with military indicators but unknown nationality |

**Military flight fields:** flight_id, callsign, nationality, branch, role (transport/ISR/tanker/VIP/trainer/fighter), aircraft_type, aircraft_description, origin, destination, confidence (high/medium/low), classification_method (callsign_pattern/aircraft_type/hex_range/category_tag)

### Logic
1. Get flights from local DB or upstream, filtered by area/time
2. Apply classification layers (first match wins, highest confidence first):

   **Layer 1: Known callsign prefixes** (high confidence)
   - `GAF` → German Air Force (Luftwaffe)
   - `RRR` → US Air Force (AMC)
   - `REACH` → US Air Force (airlift)
   - `DUKE` → US Army
   - `NAVY` → US Navy
   - `HERC` → Generic Hercules (C-130, check nationality by hex/registration)
   - `IAM` → Italian Air Force
   - `RAFV/RFR` → Royal Air Force (UK)
   - `COBRA/POKER/VIPER/SNAKE` → US military tactical callsigns
   - `RSD` → Russia State Transport (Rossiya)
   - `RFF` → Russian Air Force
   - `KAF` → Kuwait Air Force
   - `UAF` → Ukrainian Air Force
   - `EGF` → Egyptian Air Force
   - `BAF` → Belgian Air Force
   - `HAF` → Hellenic (Greek) Air Force
   - `JOR` → Jordanian military
   - `IAF` → Israeli Air Force (rare on ADS-B)

   **Layer 2: Aircraft type classification** (medium confidence)
   - Transport: C130, C30J, C17, A400, IL76, AN12, AN124, C5, C295, CN35
   - ISR/SIGINT: RC135, E3, E8, EP3, P8A, GLEX (some configs), BE20 (some)
   - Tanker: KC135, KC10, KC46, A330MRTT
   - VIP: C40, C32, VC25, GLF5/GLF6 (some)
   - Trainer: T6, PC21, T38, M346
   - Fighter: F15, F16, F35, F18, EF2K, RFAL

   **Layer 3: ICAO hex range** (medium confidence)
   - `738` prefix → Israel military (check specific sub-ranges)
   - `3C4-3C7` → Germany
   - `AE` prefix → US military
   - `43C` prefix → UK military

   **Layer 4: `category` tag** (from live.flight_metadata) (low confidence)
   - `category = 'Military_and_government'`
   - `military_type` field

3. Classify role based on aircraft type
4. Group by nationality and role

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Military callsign patterns | Static lookup table (built-in) | Free | N/A |
| Military ICAO hex ranges | Static lookup table (built-in) | Free | N/A |

### Implementation Notes
- Your data already has: HERC30 (C-130, Jordan), POKER45 (C560, Baghdad area), COBRA66 (BE20, Egypt), GAF901 (A321 German AF, Beirut→Amman), GAF149 (A400M German AF, Cyprus→TLV), KAF3210 (C-130J Kuwait), UAF820 (C295 Ukraine), RSD795 (IL-96 Russia, Amman→Moscow)
- Israeli Air Force rarely broadcasts ADS-B — detection relies on hex range analysis
- Russian state transport (RSD/Rossiya) flights to Amman are politically significant
- German military flights to Beirut/TLV indicate EU military engagement
- Category: **ANALYSIS**

---

## 36. `border_crossing_analyzer` — Levant Border Intelligence

**Purpose:** Analyze flights crossing ME borders, focusing on unusual or politically significant crossings. Your `crossed_borders` data shows Israel↔Jordan↔Syria↔Lebanon↔Egypt corridors. Detect flights that cross borders they normally shouldn't, or new border-crossing patterns.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `time_range_days` | NUMBER | No | Lookback period (default: 7) |
| `border_pair` | STRING | No | Specific crossing to monitor: `"Israel-Syria"`, `"Israel-Lebanon"`, `"Lebanon-Syria"`, `"Jordan-Syria"`, `"Jordan-Iraq"`, `"Egypt-Israel"`, `"all"` (default: `"all"`) |
| `exclude_known_routes` | BOOLEAN | No | Filter out routine commercial crossings (default: false) |
| `flag_sensitive` | BOOLEAN | No | Flag politically sensitive crossings (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `crossings` | JSON_OBJECT | Array of border-crossing flight records |
| `flight_ids` | LIST_OF_STRINGS | Flights with noteworthy crossings |
| `crossing_matrix` | JSON_OBJECT | Country-pair crossing counts |
| `sensitive_crossings` | JSON_OBJECT | Politically unusual crossings |
| `new_crossings` | JSON_OBJECT | Border pairs with first-time crossers |
| `trend` | JSON_OBJECT | Daily crossing counts vs baseline |

**Crossing record fields:** flight_id, callsign, airline, origin, destination, borders_crossed (list), is_sensitive, sensitivity_reason, aircraft_type, timestamp

### Logic
1. Query `live.flight_metadata` for flights with `crossed_borders IS NOT NULL`
2. Parse `crossed_borders` string into list (comma-separated)
3. For each flight, extract all border pairs (adjacent countries in crossing list)
4. Apply sensitivity rules:
   - **High**: Israel↔Syria, Israel↔Lebanon, Israel↔Iran (no diplomatic relations)
   - **Medium**: Israel↔Iraq, Syria↔Gulf states (unusual commercial routes)
   - **Low**: Israel↔Jordan, Israel↔Egypt (peace treaty, normal)
   - **Note**: flights don't cross Israeli airspace directly from Lebanon/Syria — they typically route through Jordan or Cyprus, so direct crossings are very significant
5. Compare against baseline crossing patterns — flag new border pairs
6. If `exclude_known_routes`: remove EL AL/MEA/RJ regular commercial flights
7. Build crossing frequency matrix

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Sensitivity rules | Static config (built-in) | Free | N/A |

### Implementation Notes
- `crossed_borders` field already parsed in your live pipeline — great data source
- Your data shows: "Israel,Jordan" (259), "Lebanon,Syria" (106), "Jordan,Syria" (35), "Israel,Jordan,Syria" (15), "Israel,Jordan,Lebanon,Syria" (8) — that last one is significant
- Flights crossing Israel+Jordan+Syria+Lebanon indicate long-range routing through the entire Levant
- Category: **ANALYSIS**

---

## 37. `syria_iraq_airport_monitor` — Post-Conflict Airport Activity

**Purpose:** Monitor activity at Syrian and Iraqi airports — historically closed or restricted airports reopening, new operators appearing, military vs civilian traffic ratios. Crucial for tracking reconstruction, sanctions evasion, and military logistics.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airports` | LIST_OF_STRINGS | No | ICAO codes to monitor (default: all Syrian + Iraqi airports) |
| `time_range_days` | NUMBER | No | Lookback period (default: 30) |
| `compare_baseline_days` | NUMBER | No | Historical comparison period (default: 90) |
| `alert_new_operators` | BOOLEAN | No | Flag operators not seen in baseline period (default: true) |
| `alert_military_types` | BOOLEAN | No | Flag military aircraft types (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `airport_activity` | JSON_OBJECT | Per-airport activity summary |
| `new_operators` | JSON_OBJECT | Operators appearing for first time |
| `military_traffic` | JSON_OBJECT | Military/heavy transport flights |
| `trend_comparison` | JSON_OBJECT | Current vs baseline activity per airport |
| `operator_changes` | JSON_OBJECT | Operators that started/stopped flying |
| `flight_ids` | LIST_OF_STRINGS | All matching flights |

**Airport activity fields:** icao_code, name, total_flights, unique_operators, military_count, civilian_count, avg_daily, trend_vs_baseline (percentage change), top_routes, new_since_baseline (bool)

### Logic
1. Define Syrian/Iraqi airport sets:
   - **Syria**: OSDI (Damascus), OSLK (Latakia/Bassel al-Assad), OSAP (Aleppo), OSDZ (Deir ez-Zor), OSKL (Kamishli), OSTA (Tabqa), OSPR (Palmyra/T4)
   - **Iraq**: ORBI (Baghdad), ORBS (Basra), ORER (Erbil), ORSU (Sulaymaniyah), ORNI (Najaf), ORMM (Mosul), ORKK (Kirkuk)
2. Query `research.flight_metadata` + `live.flight_metadata` for flights to/from these airports
3. For current period:
   - Count flights per airport
   - List unique operators
   - Classify military vs civilian (using callsign decoder logic + aircraft type)
4. For baseline period:
   - Same analysis
   - Compute operator set
5. Compare:
   - Activity change (flights/day vs baseline)
   - New operators (current - baseline)
   - Disappeared operators (baseline - current)
6. Flag: airports with sudden activity spikes, new military operators, unfamiliar airline codes

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Your data shows Syrian flights: SyrianAir (SYR), FlyCordoba (FYC), TurkJet (TKJ), Air Arabia, flydubai, Royal Jordanian, Turkish Airlines
- FYC (FlyCordoba) operating Erbil↔Damascus is interesting — newer operator
- Latakia (OSLK) is also Khmeimim — Russia's primary air base in Syria
- T4/Palmyra (OSPR) is known for Iranian military operations
- Category: **ANALYSIS**

---

## 38. `red_sea_corridor_monitor` — Bab el-Mandeb / Red Sea Threat Monitor

**Purpose:** Monitor aviation activity over the Red Sea and Bab el-Mandeb strait, especially relevant during Houthi missile/drone campaigns. Track diversions, military patrol flights, and correlate with vessel traffic for combined maritime-air picture.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `time_range_days` | NUMBER | No | Lookback period (default: 7) |
| `include_diversions` | BOOLEAN | No | Detect flights that diverted away from Red Sea routing (default: true) |
| `include_military` | BOOLEAN | No | Show military patrol/ISR flights (default: true) |
| `include_vessels` | BOOLEAN | No | Correlate with marine vessel data (default: true) |
| `altitude_ceiling_ft` | NUMBER | No | Only track flights below this altitude (default: 50000) |
| `zone` | STRING | No | `"bab_el_mandeb"`, `"southern_red_sea"`, `"northern_red_sea"`, `"gulf_of_aden"`, `"all"` (default: `"all"`) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `flights` | JSON_OBJECT | Flights in the Red Sea corridor |
| `military_patrols` | JSON_OBJECT | Military/ISR flights (P-8, MQ-9, etc.) |
| `diversions` | JSON_OBJECT | Flights that changed route to avoid the area |
| `vessel_activity` | JSON_OBJECT | Ships in the same area (from marine tables) |
| `traffic_density` | JSON_OBJECT | Hourly flight counts vs baseline |
| `threat_indicators` | JSON_OBJECT | Composite threat assessment |

**Diversion fields:** flight_id, callsign, planned_route (inferred from origin/dest), actual_route_deviation, avoided_area, airline

### Logic
1. Define Red Sea zones (static polygons):
   - **Bab el-Mandeb**: lat 12.0-13.5, lon 42.5-44.0
   - **Southern Red Sea**: lat 13.5-20.0, lon 38.0-44.0
   - **Northern Red Sea**: lat 20.0-28.0, lon 32.0-38.0
   - **Gulf of Aden**: lat 10.0-15.0, lon 44.0-51.0
2. Query flight tracks passing through these zones
3. Diversion detection:
   - Find flights between Europe/Med and Gulf/East Africa that normally use Red Sea
   - Check if they're routing around Africa (via FAOR) or through Iraq instead
   - Compare actual routing vs learned_paths for same origin-dest pair
4. Military patrol detection:
   - Apply military_callsign_decoder logic
   - Look for ISR patterns: P-8A, MQ-9, surveillance orbits (holding_pattern_detector)
5. If `include_vessels`:
   - Query `marine.vessel_positions` in same zones
   - Correlate military aircraft positions with vessel positions
6. Compute threat indicators:
   - Traffic density drop (airlines avoiding area)
   - Military patrol increase
   - Vessel traffic changes

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.normal_tracks` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `marine.vessel_positions` (local DB) | PostgreSQL | Free | N/A |
| `marine.vessel_metadata` (local DB) | PostgreSQL | Free | N/A |
| `public.learned_paths` / `public.learned_tubes` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Red Sea monitoring is critical since Houthi attacks on shipping started November 2023
- Many airlines rerouted away from Red Sea — detecting this is valuable
- Military patrol patterns (US Navy P-8A, coalition ISR) are trackable via ADS-B
- Cross-domain: combining flight data with vessel data gives complete tactical picture
- Category: **ANALYSIS**

---

## 39. `signal_loss_corridor_mapper` — ME Signal Degradation Patterns

**Purpose:** Map corridors where flights consistently lose signal. Your data shows El Al flights from Thailand losing signal 11-13 times, Atlas Air to TLV with 18 losses. This reveals persistent jamming/interference zones along specific routes.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `route` | STRING | No | Specific route to analyze: "ORIGIN-DESTINATION" ICAO codes |
| `airline` | STRING | No | Specific airline to analyze |
| `min_signal_losses` | NUMBER | No | Minimum signal loss events to include (default: 3) |
| `time_range_days` | NUMBER | No | Lookback period (default: 30) |
| `polygon` | JSON_OBJECT | No | Area to focus analysis |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `affected_flights` | JSON_OBJECT | Flights with signal losses above threshold |
| `loss_corridors` | JSON_OBJECT | Geographic corridors with persistent signal degradation |
| `airline_ranking` | JSON_OBJECT | Airlines ranked by average signal losses per flight |
| `route_ranking` | JSON_OBJECT | Routes ranked by average signal losses |
| `heatmap_data` | JSON_OBJECT | GeoJSON of signal loss density |
| `flight_ids` | LIST_OF_STRINGS | Affected flight IDs |

**Loss corridor fields:** corridor_id, start_lat, start_lon, end_lat, end_lon, avg_losses_per_flight, total_affected_flights, affected_airlines, geometry (GeoJSON LineString), likely_cause (jamming/coverage/terrain)

### Logic
1. Query `live.flight_metadata` WHERE `signal_loss_events >= min_signal_losses`
2. Filter by route/airline/polygon if specified
3. For affected flights, get track points from `live.normal_tracks`
4. Identify gap locations in tracks (where signal was lost and reacquired)
5. Cluster gap locations using DBSCAN to find persistent corridors
6. Cross-reference corridors with:
   - `public.jamming_grid` — if jamming cells overlap, likely cause = jamming
   - `public.coverage_grid` — if coverage is good but signal lost, suspicious
7. Rank airlines and routes by average signal loss count
8. Generate heatmap and corridor GeoJSON

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `live.normal_tracks` (local DB) | PostgreSQL | Free | N/A |
| `public.jamming_grid` (local DB) | PostgreSQL | Free | N/A |
| `public.coverage_grid` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Your data shows: EL AL from Thailand (VTSP/VTBS→LLBG) loses signal 11-13 times — these flights overfly ME jamming zones
- Atlas Air (GTI3413) VHHH→LLBG with 18 signal losses — same corridor
- KAL/EgyptAir long-haul flights to Cairo also affected
- Data quality score inversely correlates with signal losses — already computed
- Category: **ANALYSIS**

---

## 40. `airspace_rerouting_detector` — Conflict Avoidance Pattern Analysis

**Purpose:** Detect when airlines start avoiding specific airspace due to conflict or perceived threats. Compares actual routing against learned paths to identify systematic diversions. Real-time indicator of escalation/de-escalation.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `origin` | STRING | No | Origin ICAO code |
| `destination` | STRING | No | Destination ICAO code |
| `avoidance_zone` | JSON_OBJECT | No | Polygon of suspected avoidance area [[lat, lon], ...] |
| `time_range_days` | NUMBER | No | Analysis period (default: 14) |
| `baseline_days` | NUMBER | No | Normal routing baseline (default: 90) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `rerouted_flights` | JSON_OBJECT | Flights taking unusual routing |
| `avoidance_zones` | JSON_OBJECT | Detected avoidance areas (inferred from routing changes) |
| `comparison` | JSON_OBJECT | Baseline vs current route distribution |
| `affected_airlines` | LIST_OF_STRINGS | Airlines that changed routing |
| `reroute_cost` | JSON_OBJECT | Extra distance/time from diversions |
| `timeline` | JSON_OBJECT | When rerouting started |

**Reroute record fields:** flight_id, callsign, airline, origin, destination, baseline_route_id (from learned_tubes), actual_deviation_nm, extra_distance_nm, extra_time_minutes, avoidance_area_lat_lon, reroute_direction (north/south/west)

### Logic
1. Get learned routes from `public.learned_tubes` for origin-destination pair
2. Query current flights on same route from `research.flight_metadata`
3. Get track data from `research.normal_tracks`
4. For each current flight:
   - Compute lateral deviation from each known tube centerline
   - Find best-matching tube
   - If deviation > threshold from ALL known tubes → rerouted
5. If `avoidance_zone` provided:
   - Check if rerouted flights are specifically avoiding that polygon
6. If no zone provided:
   - Infer avoidance area from the gap between baseline routes and current routes
   - The "empty space" between normal and rerouted tracks = likely threat zone
7. Compute cost: extra NM distance, estimated extra fuel/time
8. Timeline: find the date when rerouting behavior started

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `public.learned_tubes` (local DB, 3,145 routes) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.normal_tracks` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- 3,145 learned tubes are the baseline — they represent "normal" routing
- When airlines start avoiding Syrian/Iranian/Iraqi airspace, their tracks deviate from these tubes
- The inferred avoidance zone (negative space analysis) is particularly powerful — it shows what airspace is perceived as dangerous even without official NOTAMs
- Category: **ANALYSIS**

---

## 41. `gulf_sanctions_hub_tracker` — UAE/Qatar/Bahrain Transshipment Monitor

**Purpose:** Track flights using Gulf airports as transshipment/refueling points between sanctioned and non-sanctioned territories. Gulf states are documented transshipment hubs for sanctions evasion — an aircraft from Iran stops in Dubai before continuing to Africa or Asia.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `hub_airports` | LIST_OF_STRINGS | No | Gulf hub airports (default: OMDB, OMAA, OMSJ, OTHH, OBBI, OERK, OEJN) |
| `time_range_days` | NUMBER | No | Lookback period (default: 30) |
| `min_dwell_hours` | NUMBER | No | Minimum time on ground to count as a stop (default: 1) |
| `max_dwell_hours` | NUMBER | No | Maximum (filter out based aircraft) (default: 48) |
| `flag_sanctioned_connections` | BOOLEAN | No | Flag stops connecting from/to sanctioned territories (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `transit_flights` | JSON_OBJECT | Flights using Gulf hubs as transit |
| `suspicious_transits` | JSON_OBJECT | Transits connecting sanctioned ↔ non-sanctioned |
| `hub_activity` | JSON_OBJECT | Per-hub transit statistics |
| `operator_patterns` | JSON_OBJECT | Operators with repeat transit patterns |
| `flight_ids` | LIST_OF_STRINGS | Flagged flight IDs |
| `network` | JSON_OBJECT | Origin → Hub → Destination flow network |

**Transit flight fields:** flight_id, registration, operator, inbound_origin, hub_airport, outbound_destination, dwell_hours, inbound_timestamp, outbound_timestamp, is_sanctioned_connection, sanctioned_end (origin/destination), connection_type (turnaround/transit/repositioning)

### Logic
1. Query `live.flight_metadata` for flights arriving at Gulf hub airports
2. For each arriving aircraft:
   - Find the next departure by same registration/hex within `max_dwell_hours`
   - Compute dwell time
   - Build inbound-origin → hub → outbound-destination chain
3. Flag sanctioned connections:
   - Inbound from Iran (OI*), Syria (OS*), Yemen (OY*) → hub → anywhere
   - Anywhere → hub → sanctioned territory
   - Both legs connecting sanctioned territories via hub
4. Identify repeat patterns (same operator, same routing, regular schedule)
5. Build flow network: origin → hub → destination with edge weights

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| `research.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Sanctioned airport prefixes | Static config (built-in) | Free | N/A |

### Implementation Notes
- OMDB (Dubai), OMSJ (Sharjah), OMAA (Abu Dhabi) are known transshipment points
- Track by registration (not flight number) to follow physical aircraft through stops
- Dwell time 1-6 hours = typical transit; < 1 hour = technical stop; > 48 hours = based aircraft
- FR24 historical data can extend this analysis further back for pattern establishment
- Category: **ANALYSIS**

---

## 42. `me_anomaly_enricher` — Middle East Anomaly Context Layer

**Purpose:** Enrich anomaly reports with Middle East operational context. Takes raw anomaly data and adds: nearest conflict zone, sanctions relevance, military activity correlation, jamming zone proximity, and border crossing context. Turns raw data points into intelligence.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result from upstream (anomaly cube output) |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs with anomalies |
| `include_context` | LIST_OF_STRINGS | No | Context layers: `"conflict"`, `"sanctions"`, `"military"`, `"jamming"`, `"border"`, `"all"` (default: `"all"`) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `enriched_anomalies` | JSON_OBJECT | Anomaly records with ME context added |
| `high_interest` | JSON_OBJECT | Anomalies with multiple context flags |
| `context_summary` | JSON_OBJECT | Aggregate: how many anomalies near conflict, near jamming, etc. |
| `flight_ids` | LIST_OF_STRINGS | Flight IDs with enriched anomalies |

**Enrichment fields added:** nearest_conflict_zone (name + distance), sanctions_relevant (bool + reason), military_activity_nearby (bool + details), in_jamming_zone (bool + zone_name + intensity), border_context (which borders, sensitivity), composite_interest_score (0-100)

### Logic
1. Get anomaly records from upstream or query `research.anomaly_reports`
2. For each anomaly, apply context layers:
   - **Conflict**: distance to known conflict zones (Gaza, Syria, Yemen, Iraq), using predefined polygons
   - **Sanctions**: check if flight operator/registration matches known sanctioned entities
   - **Military**: check `live.flight_metadata` for military flights in same area ± 30 minutes
   - **Jamming**: check `public.jamming_grid` for active jamming at anomaly location
   - **Border**: check `crossed_borders` data for unusual border crossings
3. Compute composite interest score:
   - Near conflict zone: +20
   - Sanctions-relevant: +30
   - Military activity nearby: +15
   - In active jamming zone: +10
   - Unusual border crossing: +15
   - High anomaly severity: +10
4. Sort by composite score, return top results as high_interest

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.anomaly_reports` (local DB) | PostgreSQL | Free | N/A |
| `public.jamming_grid` (local DB) | PostgreSQL | Free | N/A |
| `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Conflict zone polygons | Static GeoJSON (built-in) | Free | N/A |
| Sanctioned operators list | Static JSON (built-in) | Free | N/A |

### Implementation Notes
- This is a "force multiplier" cube — takes existing anomaly output and adds context
- Chains naturally after `get_anomalies` or `signal_health_analyzer`
- Composite score enables prioritization — analysts look at 90+ scores first
- All data sources are local — fast execution, no external API calls
- Category: **ANALYSIS**
