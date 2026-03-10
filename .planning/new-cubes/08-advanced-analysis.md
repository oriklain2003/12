# Category VIII: Advanced Analysis Cubes

## 23. `set_operations` — Flight Set Algebra

**Purpose:** Perform set operations (union, intersection, difference, symmetric difference) on two lists of flight IDs. Simple but essential for building complex boolean filter chains in the visual workflow — "flights in area A that are NOT in area B", "flights matching BOTH squawk filter AND altitude filter", etc.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `set_a` | LIST_OF_STRINGS | Yes | First set of IDs (flight_ids or hex_list) |
| `set_b` | LIST_OF_STRINGS | Yes | Second set of IDs |
| `operation` | STRING | No | `"intersection"`, `"union"`, `"difference"` (A-B), `"symmetric_difference"` (default: `"intersection"`) |
| `full_result_a` | JSON_OBJECT | No | Accepts full result for set A (extracts flight_ids or hex_list) |
| `full_result_b` | JSON_OBJECT | No | Accepts full result for set B |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `result` | LIST_OF_STRINGS | Resulting ID list |
| `count` | NUMBER | Number of IDs in result |
| `set_a_count` | NUMBER | Original size of set A |
| `set_b_count` | NUMBER | Original size of set B |
| `operation_summary` | STRING | Human-readable: "142 flights in A ∩ B (from 500 in A, 300 in B)" |

### Logic
1. Extract ID lists from inputs (direct or from full_result)
2. Convert to Python sets
3. Apply operation:
   - `intersection`: `set_a & set_b`
   - `union`: `set_a | set_b`
   - `difference`: `set_a - set_b`
   - `symmetric_difference`: `set_a ^ set_b`
4. Return result as sorted list

### Data Sources
None — pure logic cube.

### Implementation Notes
- Zero external dependencies — pure Python set operations
- Crucial for workflow expressiveness despite simplicity
- Handles both `flight_ids` (FR provider) and `hex_list` (Alison provider) — detects from full_result
- Category: **FILTER**

---

## 24. `network_graph_builder` — Entity Relationship Mapping

**Purpose:** Build entity-relationship graphs from flight data. Connects aircraft to airports, operators, owners, and co-located aircraft. Enables visual exploration of connection networks.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result (extracts flights with metadata) |
| `flights` | JSON_OBJECT | No | Array of flight records with metadata |
| `graph_type` | STRING | No | `"airport_network"` (aircraft↔airports), `"operator_network"` (aircraft↔operators), `"co_location"` (aircraft↔aircraft via shared airports), `"full"` (all) (default: `"airport_network"`) |
| `min_edge_weight` | NUMBER | No | Minimum connections to include an edge (default: 1) |
| `include_metadata` | BOOLEAN | No | Attach enrichment data to nodes (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `nodes` | JSON_OBJECT | Array of graph nodes with type, label, metadata |
| `edges` | JSON_OBJECT | Array of graph edges with source, target, weight, metadata |
| `communities` | JSON_OBJECT | Detected communities/clusters of related entities |
| `central_nodes` | JSON_OBJECT | Top nodes by degree centrality |
| `stats` | JSON_OBJECT | Graph statistics: node count, edge count, density, components |

**Node fields:** id, type (aircraft/airport/operator/country), label, metadata (varies by type), degree, community_id

**Edge fields:** source, target, weight (number of flights), edge_type (flies_to, operated_by, co_located_with), metadata (dates, flight_ids)

### Logic
1. Extract flight records from input
2. Build graph based on `graph_type`:
   - **airport_network**: nodes = aircraft + airports; edges = aircraft → airport (weighted by visit count)
   - **operator_network**: nodes = aircraft + operators; edges = aircraft → operator
   - **co_location**: nodes = aircraft; edges = aircraft ↔ aircraft if they visited same airport within time window
   - **full**: all of the above combined
3. Compute graph metrics:
   - Degree centrality (most connected nodes)
   - Community detection (Louvain algorithm or connected components)
4. Filter by `min_edge_weight` to reduce noise
5. Return graph data in format suitable for frontend visualization (e.g., D3.js force-directed or Cytoscape)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| Upstream cube data (via full_result) | In-memory | Free | N/A |

### Implementation Notes
- Use `networkx` for graph operations (already common Python dependency)
- Community detection via `networkx.algorithms.community`
- The output format should be compatible with common graph visualization libraries
- Widget hint: `"network_graph"` for a dedicated frontend graph widget
- Category: **ANALYSIS**

---

## 25. `temporal_heatmap` — Time-Series Activity Analysis

**Purpose:** Aggregate flight activity over time and detect temporal patterns: cyclical schedules, trend changes, burst activity, and anomalous quiet periods. Produces data suitable for calendar heatmap or time-series chart visualization.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `full_result` | JSON_OBJECT | No | Accepts full result (extracts flights with timestamps) |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs to analyze |
| `granularity` | STRING | No | `"hourly"`, `"daily"`, `"weekly"` (default: `"daily"`) |
| `time_range_days` | NUMBER | No | Analysis period (default: 30) |
| `group_by` | STRING | No | Optional grouping field: `"airline"`, `"aircraft_type"`, `"origin"`, `"destination"`, `"category"` |
| `detect_anomalies` | BOOLEAN | No | Flag unusual periods (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `time_series` | JSON_OBJECT | Array of {period, count, [group]} records |
| `anomalous_periods` | JSON_OBJECT | Periods with counts outside 2 stddev |
| `trends` | JSON_OBJECT | Trend direction (increasing/decreasing/stable), slope |
| `cyclical_pattern` | JSON_OBJECT | Detected day-of-week or hour-of-day patterns |
| `summary` | JSON_OBJECT | Total flights, avg per period, peak period, quiet period |

### Logic
1. Get flight timestamps from local DB or upstream full_result
2. Bucket flights into time periods based on `granularity`
3. If `group_by` specified: compute counts per group per period
4. Compute statistics:
   - Mean and stddev of counts per period
   - Day-of-week pattern (for daily/weekly granularity)
   - Hour-of-day pattern (for hourly granularity)
   - Linear trend (slope via simple regression)
5. If `detect_anomalies`:
   - Flag periods where count > mean + 2*stddev (spike) or < mean - 2*stddev (drop)
6. Return structured time-series data

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.flight_metadata` / `live.flight_metadata` (local DB) | PostgreSQL | Free | N/A |
| Upstream cube data (via full_result) | In-memory | Free | N/A |

### Implementation Notes
- Uses pandas for time-series bucketing and statistics
- Widget hint: `"calendar_heatmap"` or `"time_series_chart"` for frontend rendering
- The anomaly detection is simple (z-score) but effective for flight count data
- Can chain after any data source cube to analyze temporal patterns
- Category: **AGGREGATION**

---

## 26. `proximity_detector` — Aircraft Proximity Events

**Purpose:** Detect spatial-temporal proximity between two sets of aircraft tracks. Identifies formation flying, escort patterns, near-misses, and interception trajectories.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flight_ids_a` | LIST_OF_STRINGS | Yes | First group of flights |
| `flight_ids_b` | LIST_OF_STRINGS | No | Second group (if empty, checks within group A) |
| `hex_list_a` | LIST_OF_STRINGS | No | Alternative: Alison hex addresses for group A |
| `hex_list_b` | LIST_OF_STRINGS | No | Alternative: Alison hex addresses for group B |
| `provider` | STRING | No | `"fr"` or `"alison"` (default: `"fr"`) |
| `max_distance_nm` | NUMBER | No | Maximum horizontal distance for proximity event (default: 5) |
| `max_altitude_diff_ft` | NUMBER | No | Maximum vertical separation (default: 2000) |
| `min_duration_seconds` | NUMBER | No | Minimum proximity duration to report (default: 30) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `events` | JSON_OBJECT | Array of proximity events |
| `pairs` | JSON_OBJECT | Unique aircraft pairs with events |
| `count` | NUMBER | Total proximity events |
| `map_data` | JSON_OBJECT | GeoJSON with both tracks highlighted at proximity points |

**Proximity event fields:** aircraft_a (flight_id/hex), aircraft_b (flight_id/hex), start_ts, end_ts, duration_seconds, min_distance_nm, min_altitude_diff_ft, closure_rate_kts, classification (formation, escort, converging, crossing, parallel), center_lat, center_lon, geometry (GeoJSON MultiLineString showing both tracks during event)

### Logic
1. Get track points for all aircraft from local DB
2. Build spatial-temporal index:
   - Bucket track points into time slices (e.g., 10-second windows)
   - For each time slice, find pairs of aircraft within `max_distance_nm` using KD-tree
3. For each proximity pair:
   - Compute precise distance using haversine
   - Check altitude separation
   - Track duration of continuous proximity
   - Compute closure rate (are they converging, diverging, or parallel?)
4. Classify proximity type:
   - **Formation**: sustained parallel track, similar altitude, same direction
   - **Escort**: one aircraft following another's route
   - **Converging**: decreasing distance → potential intercept
   - **Crossing**: brief proximity at crossing tracks
   - **Parallel**: same direction, sustained distance
5. Generate GeoJSON showing both tracks with proximity segments highlighted

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `research.normal_tracks` / `public.positions` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- KD-tree (from scipy.spatial) for efficient spatial queries
- Time-bucketing reduces O(n²) pair comparisons significantly
- Haversine distance for geographic accuracy at all latitudes
- 1 NM ≈ 1.852 km — use this conversion consistently
- Category: **ANALYSIS**
