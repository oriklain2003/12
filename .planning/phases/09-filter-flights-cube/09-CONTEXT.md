# Phase 9: Filter Flights Cube - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement a behavioral Filter Flights cube (category: filter) that accepts flight_ids + full_result from AllFlights, evaluates track data from research.normal_tracks against user-defined thresholds, and outputs only flights that pass ALL criteria. Includes polygon geofence filtering. Must be fast at scale — this is a "narrow down to interesting flights" tool.

</domain>

<decisions>
## Implementation Decisions

### Filter logic
- AND logic — every active threshold must pass for a flight to be included
- Flights with no track data in normal_tracks are excluded (no data = can't verify = skip)
- All threshold params are optional — only active ones are evaluated

### Input design
- Accepts `full_result` from AllFlights (accepts_full_result: true) — gets the flights array + flight_ids
- Also accepts individual filter params: max_altitude_ft, min_speed_knots, max_speed_knots, min_duration_minutes, max_duration_minutes
- Polygon input (JSON_OBJECT, widget_hint: polygon) for geofence — same pattern as AllFlights

### Performance strategy — two-tier filtering
- **Tier 1 (cheap — flight_metadata via full_result):** Duration filtering uses first_seen_ts/last_seen_ts from the AllFlights full_result data (timestamps match normal_tracks exactly, verified on live data). Filter out flights by duration BEFORE querying normal_tracks.
- **Tier 2 (expensive — normal_tracks query):** Only query track data for flights that survived Tier 1. Use SQL-level GROUP BY aggregation (MIN/MAX alt, MIN/MAX gspeed) rather than fetching all points to Python. Polygon check requires per-point evaluation — use bounding box SQL pre-filter + Python ray-casting (same pattern as AllFlights).
- This avoids querying normal_tracks for flights already excluded by duration, which is the biggest performance win.

### Polygon filtering
- Same approach as AllFlights: bounding box SQL pre-filter on lat/lon, then Python-side ray-casting per track point
- A flight passes if ANY of its track points falls inside the polygon (flight traversed the area)
- Reuse the existing `point_in_polygon` function from all_flights.py (or extract to shared util)

### Output shape
- `filtered_flight_ids`: LIST_OF_STRINGS — flight_ids that passed all filters
- `filtered_flights`: JSON_OBJECT — the full flight metadata rows from the input full_result, filtered down to passing flights (preserves all columns from AllFlights output)
- No new columns added — the output is a subset of the input data

### Duration source
- Duration computed from flight_metadata first_seen_ts/last_seen_ts (available in AllFlights full_result)
- Verified: timestamps match normal_tracks MIN/MAX to within 0.0 minutes on live data
- No need to query normal_tracks for duration — saves a round trip

### Track data units
- alt column: feet (verified: max ~38,000 for commercial flights)
- gspeed column: knots (verified: max ~555 for jets)
- These match the param names (max_altitude_ft, min_speed_knots, etc.)

</decisions>

<specifics>
## Specific Ideas

- "The idea is to be very fast — user wants to narrow down to only flights they're interested in"
- Two-tier approach: filter what you can from metadata first, only hit normal_tracks for what remains
- SQL GROUP BY for aggregate stats (don't fetch all track points to Python for altitude/speed checks)
- Polygon uses same proven pattern as AllFlights (bounding box pre-filter + ray-casting)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `all_flights.py:point_in_polygon()` — Ray-casting function for polygon geofence, can be extracted to shared util
- `all_flights.py` polygon filtering pattern — bounding box SQL pre-filter + Python-side ray-casting with early-exit per flight
- `BaseCube` base class with auto Full Result output
- Empty flight_ids guard pattern (GetAnomalies, GetFlightCourse)

### Established Patterns
- SQL built via string parts + parameterized dict (all cubes use this)
- `engine.connect()` direct usage (not FastAPI DI) for database access
- LIMIT 5000 safety cap on queries
- `accepts_full_result: true` on input params that receive full_result bundles

### Integration Points
- AllFlights outputs `flights` (JSON array) and `flight_ids` (string array) — Filter Flights receives these via full_result connection
- Downstream: GetAnomalies accepts `flight_ids` (LIST_OF_STRINGS) — direct connection from filtered_flight_ids
- Downstream: CountByField accepts any data via full_result
- 4-cube pipeline: AllFlights -> FilterFlights -> GetAnomalies -> CountByField

### Database Schema (research.normal_tracks)
- Columns: flight_id, timestamp, lat, lon, alt (feet), gspeed (knots), vspeed, track, squawk, callsign, source
- Indexed by flight_id (used in WHERE clause)
- ~1,500-2,000 points per flight

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-filter-flights-cube*
*Context gathered: 2026-03-05*
