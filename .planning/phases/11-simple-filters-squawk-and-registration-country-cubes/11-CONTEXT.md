# Phase 11: Simple Filters — Squawk, Registration Country & Alison Data Source - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Three cubes:
1. **`squawk_filter`** (FILTER) — Filter flights by transponder codes with code-change event detection
2. **`registration_country_filter`** (FILTER) — Filter by aircraft registration country via ICAO24 hex prefix and tail number prefix (Alison provider only)
3. **Alison data source cube** (DATA_SOURCE) — Query `public.aircraft` + `public.positions` tables, equivalent to AllFlights but for the Alison provider

Phase 11 expanded from original scope (2 cubes) to include the Alison data source cube because the filter cubes depend on the new provider's data.

</domain>

<decisions>
## Implementation Decisions

### Data Provider Model
- Two providers: **`fr`** (existing Tracer — `research` schema, identifier = `flight_id`) and **`alison`** (new — `public` schema, identifier = `hex`)
- `squawk_filter`: Supports BOTH providers via a `provider` select param (`fr` / `alison`)
- `registration_country_filter`: **Alison-only** (requires `hex` for ICAO24 prefix matching)
- Alison data source cube: Alison-only by definition

### Database Tables (Alison Provider)
- **`public.aircraft`** (35K rows): `hex` (PK, ICAO24 address), `registration` (tail number), `icao_type`, `type_description`, `category`, `first_seen`, `last_seen`
- **`public.positions`** (46M rows): `hex`, `flight` (callsign), `squawk`, `emergency`, `ts`, `lat`, `lon`, `alt_baro`, `gs`, `track`, `on_ground`, and many more ADS-B fields
- Join on `hex` between aircraft and positions

### Squawk Filter
- **Mode param**: `custom` (user enters specific codes) or `emergency` (preset codes)
- **Emergency mode with Alison provider**: Use the `positions.emergency` column directly (values: `none`, `general`, `squawk`, `hijack`, etc.) instead of matching raw squawk codes 7500/7600/7700
- **Emergency mode with FR provider**: Match squawk codes 7500, 7600, 7700 against `research.normal_tracks.squawk`
- **Code-change detection**: Query all squawk values across the flight's positions ordered by timestamp. Detect transitions between codes and record the **timestamp of each change** in the Full Result
- **Matching logic**: A flight passes if ANY position row has a matching squawk code (intersection between flight's squawk history and target code list)
- **Outputs per spec**: `flight_ids` (or hex list depending on provider), `count`, Full Result with per-flight matched code details + code-change event timestamps

### Registration Country Filter
- **Alison-only** — operates on `hex` identifiers from the Alison data source cube
- **Filter mode**: `include` (keep only matching) or `exclude` (remove matching) — select param
- **Country resolution**: Dual check — ICAO24 hex prefix range AND tail number prefix from `public.aircraft.registration`
- **Inputs**: hex list, `filter_mode`, `countries` (tags), `regions` (tags)
- **Outputs per spec**: `flight_ids` (hex list), `count`, Full Result with resolved country per hex

### Region Groups
- **Black Countries**: Iran (730-737), Syria (778-77F), Lebanon (748-74F), Iraq (728-72F), Yemen (890), Pakistan (760-767), Libya (018-01F), Algeria (0A0-0A7), Afghanistan (700), North Korea (720-727)
- **Gray Countries**: Saudi Arabia (710-717), Egypt (010-017), Jordan (740-747), Turkey (4B8-4BF), UAE (896), Qatar (06C), Oman (70C)
- Additional groups (Middle East, EU, NATO) deferred — Black + Gray are enough for Phase 11

### Static ICAO24-to-Country Lookup
- **Source**: Scrape http://www.aerotransport.org/html/ICAO_hex_decode.html for worldwide ICAO24 allocation ranges
- **Tail number prefixes**: From Wikipedia list of aircraft registration prefixes
- **Storage**: Claude's discretion — SQLite if simple enough, or a DB table. Data is small (~200-300 country range entries)

### Alison Data Source Cube
- Similar to AllFlights in input/output pattern
- **Inputs**: Time range (relative/absolute), callsign filter, hex filter, aircraft type, polygon/bbox, altitude filters — mirroring AllFlights
- **Outputs**: flights array (aircraft metadata), hex list (identifiers for downstream cubes)
- Queries `public.aircraft` joined with aggregate data from `public.positions`

</decisions>

<specifics>
## Specific Ideas

- The `positions.emergency` column provides richer emergency classification than raw squawk codes — use it when available (Alison provider)
- Code-change events should include the exact timestamp so downstream cubes (like map visualization) can show WHERE the aircraft was when the code changed
- Black/Gray country definitions come from user-provided CSVs with exact hex ranges (see `mydocs/black_countries.csv` and `mydocs/gray_countries.csv`)
- The worldwide ICAO24 lookup enables filtering by ANY country, not just Black/Gray — the region groups are convenience shortcuts

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseCube` + auto-discovery pattern: New cubes just need a file in `backend/app/cubes/`
- `AllFlightsCube` (`all_flights.py`): Template for the Alison data source cube — same input/output pattern
- `FilterFlightsCube` (`filter_flights.py`): Template for filter cubes — `full_result` / `flight_ids` input pattern, tiered filtering
- `point_in_polygon()` in `all_flights.py`: Reusable for polygon geofencing if needed
- `ParamType`, `CubeCategory`, `ParamDefinition`: All schema types ready

### Established Patterns
- Async SQLAlchemy with `engine.connect()` for all DB queries
- `text()` for raw SQL with parameterized queries
- Safety caps (LIMIT) on large queries
- Widget hints: `polygon`, `datetime`, `relative_time`, `select`, `tags`

### Integration Points
- New cubes auto-discovered by `CubeRegistry` — just place in `backend/app/cubes/`
- Frontend catalog auto-updates from `GET /api/cubes/catalog`
- Alison data source cube outputs connect to squawk_filter and registration_country_filter inputs

### Database Schema (New Provider)
- `public.aircraft`: hex, registration, icao_type, type_description, category, first_seen, last_seen
- `public.positions`: hex, flight, squawk, emergency, ts, lat, lon, alt_baro, gs, track, on_ground, + many ADS-B fields
- `research.normal_tracks`: flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source

</code_context>

<deferred>
## Deferred Ideas

- Additional region groups (Middle East, EU, NATO) — future phase or Phase 11 extension
- `country_fir` mode for area_spatial_filter — Phase 12
- Signal health analyzer classifications — Phase 14

</deferred>

---

*Phase: 11-simple-filters-squawk-and-registration-country-cubes*
*Context gathered: 2026-03-06*
