# Category V: Maritime-Aviation Correlation Cubes

## 16. `maritime_flight_correlator` — Ship-Aircraft Rendezvous Detection

**Purpose:** Detect spatial-temporal proximity between aircraft and vessels. Reveals maritime patrol patterns, ship-to-shore coordination, sanctions enforcement flights, and potential illicit ship-to-ship transfer monitoring.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flight_ids` | LIST_OF_STRINGS | No | FR flight IDs to correlate |
| `hex_list` | LIST_OF_STRINGS | No | ICAO hex addresses to correlate |
| `polygon` | JSON_OBJECT | Yes | Area of interest [[lat, lon], ...] — maritime zone |
| `time_range_hours` | NUMBER | No | Lookback period (default: 24) |
| `max_distance_nm` | NUMBER | No | Maximum aircraft-vessel distance for match (default: 5) |
| `max_altitude_ft` | NUMBER | No | Only consider aircraft below this altitude (default: 10000) |
| `vessel_types` | LIST_OF_STRINGS | No | Filter vessel types: Cargo, Tanker, Fishing, Military, etc. |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `correlations` | JSON_OBJECT | Array of aircraft-vessel proximity events |
| `flight_ids` | LIST_OF_STRINGS | Aircraft with vessel correlations |
| `vessel_mmsis` | LIST_OF_STRINGS | Vessels correlated with aircraft |
| `count` | NUMBER | Number of correlation events |
| `map_data` | JSON_OBJECT | GeoJSON with both aircraft tracks and vessel positions |

**Correlation event fields:** flight_id, hex, aircraft_callsign, vessel_mmsi, vessel_name, vessel_type, min_distance_nm, aircraft_altitude_ft, correlation_start_ts, correlation_end_ts, duration_minutes, aircraft_position (lat/lon), vessel_position (lat/lon), geometry (GeoJSON showing both tracks)

### Logic
1. Get aircraft tracks from local DB, filtered by:
   - Polygon area
   - Altitude threshold (low-flying = more interesting)
   - Time range
2. Query `marine.vessel_positions` for vessel positions in same polygon and time range
3. Join `marine.vessel_metadata` for vessel details (name, type, destination)
4. For each aircraft track point:
   - Find vessel positions within ±5 minutes and within `max_distance_nm`
   - Use haversine distance computation
5. Merge adjacent correlation points into continuous events
6. Classify correlation type:
   - **Patrol orbit**: aircraft orbiting near vessel (combine with holding_pattern_detector output)
   - **Fly-by**: single pass near vessel
   - **Extended surveillance**: prolonged proximity (> 30 min)
7. Generate combined GeoJSON for map visualization

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `marine.vessel_positions` (local DB) | PostgreSQL | Free | N/A |
| `marine.vessel_metadata` (local DB, 7K vessels) | PostgreSQL | Free | N/A |
| `research.normal_tracks` / `public.positions` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Your marine tables are completely unused — this is the first cube to unlock them
- Vessel positions table currently has limited data (466 rows) but schema is ready for growth
- Low-altitude filtering is key — aircraft at FL350 aren't interacting with ships
- Time interpolation may be needed if aircraft/vessel timestamps don't align exactly
- Category: **ANALYSIS**

---

## 17. `vessel_tracker` — Marine Vessel Data Source

**Purpose:** Query marine vessel data from the local database. Serves as the primary data source cube for maritime analysis workflows, analogous to `all_flights` for aviation.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | No | Area filter [[lat, lon], ...] |
| `mmsi_list` | LIST_OF_STRINGS | No | Specific MMSIs to query |
| `vessel_types` | LIST_OF_STRINGS | No | Filter by vessel type description (Cargo, Tanker, Tug, etc.) |
| `vessel_name` | STRING | No | Vessel name search (ILIKE pattern) |
| `destination` | STRING | No | Vessel destination filter (ILIKE pattern) |
| `time_range_hours` | NUMBER | No | Position data lookback (default: 24) |
| `min_speed` | NUMBER | No | Minimum SOG (speed over ground) in knots |
| `max_speed` | NUMBER | No | Maximum SOG in knots |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `vessels` | JSON_OBJECT | Array of vessel records with latest position and metadata |
| `mmsi_list` | LIST_OF_STRINGS | List of matching MMSIs |
| `positions` | JSON_OBJECT | GeoJSON FeatureCollection of vessel positions/tracks |
| `count` | NUMBER | Number of matching vessels |

**Vessel record fields:** mmsi, vessel_name, callsign, imo_number, vessel_type, vessel_type_description, length, width, draught, destination, latest_lat, latest_lon, latest_speed, latest_course, latest_heading, navigation_status, last_seen

### Logic
1. Query `marine.vessel_metadata` for matching vessels (by type, name, destination)
2. Join with `marine.vessel_positions` for recent positions
3. If polygon provided: filter positions using Shapely point-in-polygon
4. If speed filters: apply to SOG column
5. Compute latest position per vessel
6. Generate GeoJSON FeatureCollection for map rendering
7. Return vessel list sorted by last_seen (most recent first)

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `marine.vessel_metadata` (local DB, 7,142 vessels) | PostgreSQL | Free | N/A |
| `marine.vessel_positions` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- Direct database queries — no external API needed
- Vessel positions table has monthly partitions (2026_02 through 2026_12) — ready for growth
- Fields follow standard AIS data model
- Vessel type descriptions available: Cargo, Tanker, Tug, Unknown, etc.
- Category: **DATA_SOURCE**
