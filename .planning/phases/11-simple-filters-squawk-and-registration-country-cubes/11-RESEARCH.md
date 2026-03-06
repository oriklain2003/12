# Phase 11: Simple Filters — Squawk, Registration Country & Alison Data Source - Research

**Researched:** 2026-03-06
**Domain:** Python cube implementation — squawk filtering, ICAO24 country resolution, Alison provider DB queries
**Confidence:** HIGH

## Summary

Phase 11 delivers three new cubes: `squawk_filter` (FILTER), `registration_country_filter` (FILTER), and an Alison data source cube (DATA_SOURCE). All three follow the established cube pattern exactly — a new file in `backend/app/cubes/`, subclassing `BaseCube`, with async SQLAlchemy queries via `engine.connect()`. Auto-discovery means no registration is needed; the file just needs to exist and be importable.

The squawk filter has two providers (`fr` uses `research.normal_tracks.squawk`, `alison` uses `public.positions.squawk` and `public.positions.emergency`). The registration country filter is Alison-only and performs ICAO24 hex range lookups against a static embedded table derived from the project's `mydocs/black_countries.csv` and `mydocs/gray_countries.csv` files, extended with a wider worldwide lookup from aerotransport.org. The Alison data source cube mirrors AllFlights in structure but targets `public.aircraft` joined with `public.positions`.

The primary complexity areas are: (1) dual-provider routing in squawk_filter, (2) ICAO24 hex range arithmetic for country resolution, and (3) the squawk code-change event detection query (ordered by timestamp, detect transitions). All other aspects are straightforward extensions of existing patterns.

**Primary recommendation:** Implement three files in `backend/app/cubes/` following the AllFlights/FilterFlights template. Embed the ICAO24-to-country lookup as a Python module-level constant (dict of hex range tuples to country name). No new packages required.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Phase Boundary**
- Three cubes: `squawk_filter` (FILTER), `registration_country_filter` (FILTER), Alison data source (DATA_SOURCE)
- Phase expanded from 2 cubes to 3: filter cubes depend on the Alison provider data

**Data Provider Model**
- Two providers: `fr` (existing Tracer — `research` schema, identifier = `flight_id`) and `alison` (new — `public` schema, identifier = `hex`)
- `squawk_filter`: Supports BOTH providers via a `provider` select param (`fr` / `alison`)
- `registration_country_filter`: Alison-only (requires `hex` for ICAO24 prefix matching)
- Alison data source cube: Alison-only by definition

**Database Tables (Alison Provider)**
- `public.aircraft` (35K rows): `hex` (PK, ICAO24 address), `registration` (tail number), `icao_type`, `type_description`, `category`, `first_seen`, `last_seen`
- `public.positions` (46M rows): `hex`, `flight` (callsign), `squawk`, `emergency`, `ts`, `lat`, `lon`, `alt_baro`, `gs`, `track`, `on_ground`, and many more ADS-B fields
- Join on `hex` between aircraft and positions

**Squawk Filter**
- Mode param: `custom` (user enters specific codes) or `emergency` (preset codes)
- Emergency mode with Alison provider: Use `positions.emergency` column directly (values: `none`, `general`, `squawk`, `hijack`, etc.) instead of matching raw squawk codes 7500/7600/7700
- Emergency mode with FR provider: Match squawk codes 7500, 7600, 7700 against `research.normal_tracks.squawk`
- Code-change detection: Query all squawk values across the flight's positions ordered by timestamp. Detect transitions between codes and record the timestamp of each change in the Full Result
- Matching logic: A flight passes if ANY position row has a matching squawk code (intersection between flight's squawk history and target code list)
- Outputs per spec: `flight_ids` (or hex list depending on provider), `count`, Full Result with per-flight matched code details + code-change event timestamps

**Registration Country Filter**
- Alison-only — operates on `hex` identifiers from the Alison data source cube
- Filter mode: `include` (keep only matching) or `exclude` (remove matching) — select param
- Country resolution: Dual check — ICAO24 hex prefix range AND tail number prefix from `public.aircraft.registration`
- Inputs: hex list, `filter_mode`, `countries` (tags), `regions` (tags)
- Outputs per spec: `flight_ids` (hex list), `count`, Full Result with resolved country per hex

**Region Groups**
- Black Countries: Iran (730-737), Syria (778-77F), Lebanon (748-74F), Iraq (728-72F), Yemen (890), Pakistan (760-767), Libya (018-01F), Algeria (0A0-0A7), Afghanistan (700), North Korea (720-727)
- Gray Countries: Saudi Arabia (710-717), Egypt (010-017), Jordan (740-747), Turkey (4B8-4BF), UAE (896), Qatar (06C), Oman (70C)
- Additional groups (Middle East, EU, NATO) deferred — Black + Gray are enough for Phase 11

**Static ICAO24-to-Country Lookup**
- Source: aerotransport.org/html/ICAO_hex_decode.html for worldwide ICAO24 allocation ranges
- Tail number prefixes: Wikipedia list of aircraft registration prefixes
- Storage: Claude's discretion — SQLite if simple enough, or a DB table. Data is small (~200-300 country range entries)

**Alison Data Source Cube**
- Similar to AllFlights in input/output pattern
- Inputs: Time range (relative/absolute), callsign filter, hex filter, aircraft type, polygon/bbox, altitude filters — mirroring AllFlights
- Outputs: flights array (aircraft metadata), hex list (identifiers for downstream cubes)
- Queries `public.aircraft` joined with aggregate data from `public.positions`

### Claude's Discretion

- Storage format for the worldwide ICAO24 lookup (SQLite vs Python dict vs DB table — data is small, ~200-300 entries)

### Deferred Ideas (OUT OF SCOPE)

- Additional region groups (Middle East, EU, NATO) — future phase or Phase 11 extension
- `country_fir` mode for area_spatial_filter — Phase 12
- Signal health analyzer classifications — Phase 14
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (asyncpg) | Already installed | Async DB queries to both `research` and `public` schemas | Used by every existing cube |
| BaseCube | In-project | Cube contract + auto full_result output + auto-discovery | Required for all cubes |
| ParamType / CubeCategory / ParamDefinition | In-project schemas | Type-safe parameter definitions | Established pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `logging` | stdlib | Structured debug logging with query text | AllFlights pattern — log SQL before execution |
| Python stdlib `time` | stdlib | Compute relative time cutoff (last N seconds) | Same as AllFlights for time_range_seconds |
| Python stdlib `typing` | stdlib | Type hints | Always |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python dict for ICAO24 lookup | SQLite file | Dict is simpler, zero I/O, adequate for 200-300 entries. SQLite adds file path management and async overhead. Use dict. |
| Python dict for ICAO24 lookup | PostgreSQL table | DB table requires migration, schema change, and privileged write access. DB is read-only from this project. Use dict. |
| Inline hex range arithmetic | Pre-expanded prefix set | Range arithmetic is 5 lines of Python; prefix sets would be thousands of entries for 24-bit ICAO space. Use range arithmetic. |

**Installation:** No new packages required. All dependencies are already present.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/cubes/
├── base.py                          # BaseCube (unchanged)
├── all_flights.py                   # FR data source — point_in_polygon helper
├── filter_flights.py                # FR behavioral filter (unchanged)
├── alison_flights.py                # NEW — Alison data source cube
├── squawk_filter.py                 # NEW — dual-provider squawk filter
├── registration_country_filter.py   # NEW — ICAO24 country resolution filter
└── icao24_lookup.py                 # NEW — static ICAO24-to-country lookup table
```

The `icao24_lookup.py` module separates data from logic. It is a pure Python module with no imports beyond stdlib, importable by `registration_country_filter.py`.

### Pattern 1: Dual-Provider Routing in squawk_filter

**What:** A single cube accepts a `provider` select param and branches its SQL to either `research.normal_tracks` (FR) or `public.positions` (Alison).

**When to use:** Any cube that must support both data providers.

**Example:**
```python
# Source: CONTEXT.md locked decisions
provider = inputs.get("provider", "fr")  # "fr" or "alison"

if provider == "fr":
    # FR: squawk column in research.normal_tracks
    # identifier: flight_id
    squawk_sql = """
        SELECT flight_id AS id,
               squawk,
               timestamp AS ts
        FROM research.normal_tracks
        WHERE flight_id = ANY(:ids)
          AND squawk IS NOT NULL
        ORDER BY flight_id, timestamp
    """
    id_param = "flight_ids"
else:
    # Alison: squawk and emergency columns in public.positions
    # identifier: hex
    squawk_sql = """
        SELECT hex AS id,
               squawk,
               emergency,
               ts
        FROM public.positions
        WHERE hex = ANY(:ids)
          AND (squawk IS NOT NULL OR emergency IS NOT NULL)
        ORDER BY hex, ts
    """
    id_param = "hex_list"
```

### Pattern 2: Code-Change Event Detection

**What:** Query squawk history ordered by timestamp, detect transitions between codes, record the timestamp of each change.

**When to use:** squawk_filter full_result enrichment.

**Example:**
```python
# Source: CONTEXT.md — "detect transitions between codes and record the timestamp of each change"
# Group rows by flight identifier (flight_id or hex)
from collections import defaultdict

# After fetching squawk rows ordered by (id, ts):
squawk_history: dict[str, list[tuple]] = defaultdict(list)
for row in rows:
    squawk_history[row["id"]].append((row["ts"], row["squawk"]))

per_flight_details = {}
for fid, history in squawk_history.items():
    changes = []
    prev_code = None
    for ts, code in history:
        if code != prev_code and prev_code is not None:
            changes.append({"from": prev_code, "to": code, "ts": ts})
        prev_code = code
    per_flight_details[fid] = {
        "codes_seen": list({code for _, code in history}),
        "code_changes": changes,
    }
```

### Pattern 3: ICAO24 Hex Range Arithmetic

**What:** ICAO24 addresses are 24-bit hex strings (e.g., `"730ABC"`). Country allocations are contiguous ranges (e.g., Iran: `730000`–`737FFF`). Convert to integer, check if within range.

**When to use:** registration_country_filter country resolution from hex identifier.

**Example:**
```python
# Source: CONTEXT.md black/gray country CSVs + aerotransport.org range format
def hex_to_int(hex_str: str) -> int:
    """Convert ICAO24 hex string to integer for range comparison."""
    return int(hex_str.upper().replace(" ", ""), 16)

# ICAO24_RANGES: list of (low_int, high_int, country_name)
# Stored in icao24_lookup.py as a module-level constant

def resolve_country_from_hex(hex_addr: str, ranges: list[tuple]) -> str | None:
    """Return the country name for an ICAO24 hex address, or None if unknown."""
    addr_int = hex_to_int(hex_addr)
    for low, high, country in ranges:
        if low <= addr_int <= high:
            return country
    return None
```

### Pattern 4: Tail Number Prefix Resolution

**What:** Tail numbers encode country via prefix (e.g., `EP-` = Iran, `4X-` = Israel). Used as a secondary check alongside hex range.

**When to use:** registration_country_filter — dual check (hex range primary, tail prefix secondary).

**Example:**
```python
# Source: CONTEXT.md + mydocs/new_cubes.md
# TAIL_PREFIXES: dict mapping prefix string to country name
# Stored in icao24_lookup.py

def resolve_country_from_registration(registration: str | None, prefixes: dict[str, str]) -> str | None:
    """Return country name from tail number prefix, or None."""
    if not registration:
        return None
    reg_upper = registration.upper()
    # Try longest prefix first (some countries have 3-char prefixes)
    for length in (3, 2, 1):
        prefix = reg_upper[:length]
        if prefix in prefixes:
            return prefixes[prefix]
    return None
```

### Pattern 5: Include/Exclude Filter Logic

**What:** A `filter_mode` param (`include` or `exclude`) inverts the set of returned hex identifiers.

**When to use:** registration_country_filter.

**Example:**
```python
# Source: CONTEXT.md locked decisions
filter_mode = inputs.get("filter_mode", "include")

if filter_mode == "include":
    passing_hexes = {h for h in hex_list if resolved_countries.get(h) in target_countries}
else:  # exclude
    passing_hexes = {h for h in hex_list if resolved_countries.get(h) not in target_countries}
```

### Pattern 6: Alison Data Source (AllFlights Mirror)

**What:** Alison cube is structurally identical to AllFlights but queries `public.aircraft` joined with `public.positions`.

**When to use:** AlisonFlightsCube.execute().

**Example:**
```python
# Source: all_flights.py pattern + CONTEXT.md table definitions
sql = """
    SELECT
        a.hex,
        a.registration,
        a.icao_type,
        a.type_description,
        a.category,
        a.first_seen,
        a.last_seen,
        p.flight AS callsign,
        MIN(p.ts) AS first_pos_ts,
        MAX(p.ts) AS last_pos_ts,
        MIN(p.alt_baro) AS min_alt_baro,
        MAX(p.alt_baro) AS max_alt_baro
    FROM public.aircraft a
    JOIN public.positions p ON a.hex = p.hex
    WHERE 1=1
    {filters}
    GROUP BY a.hex, a.registration, a.icao_type, a.type_description, a.category,
             a.first_seen, a.last_seen, p.flight
    LIMIT 5000
"""
# Outputs: flights (array), hex_list (LIST_OF_STRINGS)
```

### Anti-Patterns to Avoid

- **Querying all 46M positions rows without filtering by hex or time:** Always filter by `hex = ANY(:hex_list)` or a time window before fetching squawk history — positions is large.
- **Using INTEGER squawk comparison with string squawk values:** Squawk codes may be stored as strings (e.g., `"7500"`) in positions table. Use string comparison or cast explicitly. Verify column type before writing comparison logic.
- **Returning unresolved hexes silently:** If a hex is not in the ICAO24 lookup, still include it in Full Result with `country: null` so downstream cubes have full visibility.
- **Hardcoding emergency squawk codes when Alison emergency column is available:** For Alison emergency mode, use `positions.emergency != 'none'` — this is richer than matching raw codes.
- **No LIMIT on positions queries:** Always cap large table fetches. For squawk history queries, a per-hex LIMIT or time-window filter is required.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cube registration | Manual registry entries | BaseCube auto-discovery via `pkgutil.iter_modules` | CubeRegistry scans the cubes package and imports all modules — zero registration needed |
| ICAO24 lookup DB | External SQLite file, DB table | Python module-level list of (low_int, high_int, country) tuples | 200-300 entries; fits in memory; zero I/O; testable in isolation |
| Async DB pattern | Custom connection handling | `async with engine.connect() as conn` | Established pattern from all_flights.py — handles pooling, cleanup, errors |
| Squawk code parsing | Custom transponder protocol parser | Direct column reads from `squawk` and `emergency` columns | Database already stores parsed values; no protocol knowledge needed |

**Key insight:** The ICAO24 hex range lookup is the only genuinely new logic in this phase. Everything else is remixing existing patterns with different SQL.

## Common Pitfalls

### Pitfall 1: Squawk Column Type Mismatch
**What goes wrong:** `positions.squawk` may be stored as VARCHAR (e.g., `"7500"`) while user input codes are integers, causing no matches.
**Why it happens:** ADS-B data varies by source; Alison normalizes squawk as strings.
**How to avoid:** Cast input codes to string for comparison (`str(code)` or SQL `CAST(:code AS VARCHAR)`). Verify actual column type with a quick DB inspection query before writing comparison logic.
**Warning signs:** Emergency mode always returns zero results despite known emergency traffic in time window.

### Pitfall 2: Positions Table Size — Missing Time Filter
**What goes wrong:** Querying `public.positions WHERE hex = ANY(:ids)` without a time filter against 46M rows is extremely slow.
**Why it happens:** The squawk history query needs all rows per hex, so developers skip the time filter.
**How to avoid:** Require a time window input on squawk_filter and pass it through to the positions query. Alternatively, derive the time range from the Alison cube's output if time was already filtered upstream. At minimum, apply a LIMIT per hex.
**Warning signs:** Cube execution timeout; SSE stream shows cube running for >30 seconds.

### Pitfall 3: ICAO24 Lookup Order — Overlapping Ranges
**What goes wrong:** Some ICAO24 allocation ranges may overlap (rare, but possible with outdated data). First-match logic returns wrong country.
**Why it happens:** The aerotransport.org data may contain legacy overlaps or data entry errors.
**How to avoid:** Sort ranges by specificity (narrower range first). Log when a hex matches multiple entries. For the project's Black/Gray country data from CSVs, the ranges are verified and non-overlapping.
**Warning signs:** Aircraft registered in Iran matching as Pakistan (neighboring range boundary errors).

### Pitfall 4: Empty hex_list Guard
**What goes wrong:** `hex = ANY(:hex_list)` with an empty list raises a PostgreSQL type error.
**Why it happens:** Upstream Alison cube returns zero results; filter cube receives empty input.
**How to avoid:** Guard at the top of execute(): `if not hex_list: return {"flight_ids": [], "count": 0}`. Same pattern as FilterFlightsCube and GetAnomalies.
**Warning signs:** 500 error from backend on empty-input execution.

### Pitfall 5: Code-Change Detection Off-By-One
**What goes wrong:** First squawk code in history is recorded as a "change" (previous code was None).
**Why it happens:** Naive transition detection initializes `prev_code = None` and records a change on first row.
**How to avoid:** Only record a change when `prev_code is not None AND code != prev_code`. The first code establishes the baseline; only subsequent differences are events.
**Warning signs:** Full Result shows a change at the very first position timestamp for every flight.

### Pitfall 6: Provider Mismatch on flight_ids vs hex
**What goes wrong:** squawk_filter receives FR flight_ids but is set to Alison provider (or vice versa), causing zero matches.
**Why it happens:** User wires AllFlights → squawk_filter but forgets to set provider to `fr`.
**How to avoid:** Default `provider` to `fr` (most common). Document clearly in param description which input param (`flight_ids` vs `hex_list`) is active for each provider. Consider input param `flight_ids` that is used for FR and `hex_list` for Alison — make them separate named inputs.
**Warning signs:** Cube returns 0 count with non-empty input.

## Code Examples

Verified patterns from official sources:

### ICAO24 Lookup Module Structure (icao24_lookup.py)
```python
# Source: mydocs/black_countries.csv + mydocs/gray_countries.csv + CONTEXT.md
# Format: (low_int, high_int, country_name, region)
# hex values converted: 0x730000 = 7536640, etc.

ICAO24_RANGES: list[tuple[int, int, str, str]] = [
    # Black Countries
    (0x730000, 0x737FFF, "Iran", "black"),
    (0x778000, 0x77FFFF, "Syria", "black"),
    (0x748000, 0x74FFFF, "Lebanon", "black"),
    (0x728000, 0x72FFFF, "Iraq", "black"),
    (0x890000, 0x890FFF, "Yemen", "black"),
    (0x760000, 0x767FFF, "Pakistan", "black"),
    (0x018000, 0x01FFFF, "Libya", "black"),
    (0x0A0000, 0x0A7FFF, "Algeria", "black"),
    (0x700000, 0x700FFF, "Afghanistan", "black"),
    (0x720000, 0x727FFF, "North Korea", "black"),
    # Gray Countries
    (0x710000, 0x717FFF, "Saudi Arabia", "gray"),
    (0x010000, 0x017FFF, "Egypt", "gray"),
    (0x740000, 0x747FFF, "Jordan", "gray"),
    (0x4B8000, 0x4BFFFF, "Turkey", "gray"),
    (0x896000, 0x896FFF, "UAE", "gray"),
    (0x06C000, 0x06CFFF, "Qatar", "gray"),
    (0x70C000, 0x70C3FF, "Oman", "gray"),
    # ... worldwide entries from aerotransport.org to be added ...
]

REGION_GROUPS: dict[str, set[str]] = {
    "black": {"Iran", "Syria", "Lebanon", "Iraq", "Yemen", "Pakistan",
              "Libya", "Algeria", "Afghanistan", "North Korea"},
    "gray": {"Saudi Arabia", "Egypt", "Jordan", "Turkey", "UAE", "Qatar", "Oman"},
}

TAIL_PREFIXES: dict[str, str] = {
    "EP-": "Iran",
    "YK-": "Syria",
    "OD-": "Lebanon",
    "YI-": "Iraq",
    "4W-": "Yemen",
    "AP-": "Pakistan",
    "5A-": "Libya",
    "7T-": "Algeria",
    "YA-": "Afghanistan",
    "P-": "North Korea",
    "HZ-": "Saudi Arabia",
    "SU-": "Egypt",
    "JY-": "Jordan",
    "TC-": "Turkey",
    "A6-": "UAE",
    "A7-": "Qatar",
    "A4O-": "Oman",
    # ... additional worldwide entries ...
}
```

### squawk_filter — FR Provider Squawk History Query
```python
# Source: CONTEXT.md + existing research.normal_tracks schema
async with engine.connect() as conn:
    result = await conn.execute(
        text("""
            SELECT flight_id AS id,
                   squawk,
                   timestamp AS ts
            FROM research.normal_tracks
            WHERE flight_id = ANY(:ids)
              AND squawk IS NOT NULL
            ORDER BY flight_id, timestamp
        """),
        {"ids": list(flight_ids)},
    )
    rows = result.fetchall()
```

### squawk_filter — Alison Emergency Mode Query
```python
# Source: CONTEXT.md — use positions.emergency column for Alison emergency mode
async with engine.connect() as conn:
    result = await conn.execute(
        text("""
            SELECT hex AS id,
                   squawk,
                   emergency,
                   ts
            FROM public.positions
            WHERE hex = ANY(:ids)
              AND ts BETWEEN :start_ts AND :end_ts
              AND emergency IS NOT NULL
              AND emergency != 'none'
            ORDER BY hex, ts
        """),
        {"ids": list(hex_list), "start_ts": start_ts, "end_ts": end_ts},
    )
```

### registration_country_filter — Fetch hex + registration from Alison
```python
# Source: CONTEXT.md — public.aircraft table schema
async with engine.connect() as conn:
    result = await conn.execute(
        text("""
            SELECT hex, registration
            FROM public.aircraft
            WHERE hex = ANY(:hex_list)
        """),
        {"hex_list": list(hex_list)},
    )
    aircraft_rows = {row[0]: row[1] for row in result.fetchall()}
    # aircraft_rows: {hex: registration}
```

### AlisonFlightsCube — Core Query
```python
# Source: CONTEXT.md table definitions + AllFlights pattern
sql_parts = ["""
    SELECT
        a.hex,
        a.registration,
        a.icao_type,
        a.type_description,
        a.category,
        MIN(p.ts) AS first_seen_ts,
        MAX(p.ts) AS last_seen_ts,
        p.flight AS callsign
    FROM public.aircraft a
    JOIN public.positions p ON a.hex = p.hex
    WHERE 1=1
"""]
# Add time, callsign, hex, aircraft type, bbox filters — same structure as AllFlights
# GROUP BY a.hex, a.registration, a.icao_type, a.type_description, a.category, p.flight
# LIMIT 5000
```

### Cube Output Shape — squawk_filter
```python
# Source: CONTEXT.md outputs spec
return {
    "flight_ids": list(passing_ids),  # or hex_list for Alison
    "count": len(passing_ids),
    # __full_result__ auto-appended by BaseCube.definition
    # Full Result includes per_flight_details with matched codes + change events
}
```

### Cube Output Shape — registration_country_filter
```python
# Source: CONTEXT.md outputs spec
return {
    "flight_ids": list(passing_hexes),
    "count": len(passing_hexes),
    # Full Result includes: {hex: {country: str, registration: str, match_type: "hex_range"|"tail_prefix"|"unknown"}}
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single provider (FR only) | Dual provider (FR + Alison) | Phase 11 (new) | New DB schema; `hex` replaces `flight_id` as identifier for Alison cubes |
| External PostGIS for polygon | Python ray-casting | Phase 2 decision | Permanent — PostGIS not on Tracer 42 RDS |
| Manual cube registration | BaseCube auto-discovery | Phase 2 | Zero-registration — add file, done |
| DB lookup for country resolution | Static Python dict | Phase 11 (new) | No migration needed; data fits in memory |

**Deprecated/outdated:**
- Comparing squawk to emergency codes (7500/7600/7700) for Alison provider: replaced by `positions.emergency` column which provides richer classification.

## Open Questions

1. **Squawk column type in public.positions**
   - What we know: Column is named `squawk` per CONTEXT.md. Type not explicitly confirmed.
   - What's unclear: VARCHAR vs INTEGER storage. This affects comparison logic in custom mode.
   - Recommendation: Add a DB type inspection step (first task of Wave 1) before writing squawk comparison. Query: `SELECT pg_typeof(squawk) FROM public.positions LIMIT 1`.

2. **Time filter on squawk history for Alison positions**
   - What we know: public.positions has 46M rows. Must filter by time to avoid full-table scans.
   - What's unclear: Whether the squawk_filter should accept its own time params, or inherit the time window from the Alison cube upstream via full_result.
   - Recommendation: Accept `hex_list` from upstream (already time-filtered by Alison cube). Add an optional `lookback_hours` param as a safety cap. Default to 24 hours if not provided.

3. **Worldwide ICAO24 lookup coverage**
   - What we know: Black/Gray countries (17 entries) are documented in mydocs CSVs. Aerotransport.org has worldwide data (~200 entries).
   - What's unclear: Whether the planner task should include manually transcribing aerotransport.org data or just use Black/Gray for Phase 11.
   - Recommendation: Phase 11 ships with Black/Gray + a representative subset of common countries (Russia, China, Israel, US, UK, France, Germany). Full worldwide coverage is a follow-on task. The lookup module is extensible — add entries without changing logic.

4. **AlisonFlights GROUP BY callsign**
   - What we know: `public.positions.flight` is the callsign. A single hex may have multiple callsigns across different flights in the positions table.
   - What's unclear: Whether to GROUP BY callsign (returning multiple rows per hex) or aggregate callsigns into an array (one row per hex).
   - Recommendation: One row per hex, aggregate callsigns as an array (`array_agg(DISTINCT p.flight)`) to keep output consistent with AllFlights structure (one row per aircraft).

## Sources

### Primary (HIGH confidence)
- In-codebase: `backend/app/cubes/all_flights.py` — AllFlights query pattern, point_in_polygon, time filter approach
- In-codebase: `backend/app/cubes/filter_flights.py` — full_result extraction, empty guard, two-tier pattern
- In-codebase: `backend/app/cubes/base.py` — BaseCube contract, full_result auto-append
- In-codebase: `backend/app/engine/registry.py` — pkgutil auto-discovery, no registration needed
- In-codebase: `backend/app/schemas/cube.py` — ParamType, CubeCategory, ParamDefinition
- In-codebase: `mydocs/black_countries.csv` — Iran, Syria, Lebanon, Iraq, Yemen, Pakistan, Libya, Algeria, Afghanistan, North Korea hex ranges
- In-codebase: `mydocs/gray_countries.csv` — Saudi Arabia, Egypt, Jordan, Turkey, UAE, Qatar, Oman hex ranges
- `.planning/phases/11-simple-filters-squawk-and-registration-country-cubes/11-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `mydocs/new_cubes.md` — Hebrew-language cube specs with squawk filter logic detail and registration filter description
- `.planning/STATE.md` — v2.0 roadmap context; existing tech debt inventory

### Tertiary (LOW confidence)
- aerotransport.org/html/ICAO_hex_decode.html — worldwide ICAO24 allocation (not fetched during this research; Black/Gray data verified via CSVs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — identical to existing cubes, no new libraries
- Architecture: HIGH — provider routing and ICAO24 arithmetic are straightforward; patterns derived from CONTEXT.md + code inspection
- Pitfalls: HIGH — most identified by analogy with existing bugs (empty guard fixed in GetAnomalies, squawk type issues common in ADS-B data)
- ICAO24 lookup data: MEDIUM — Black/Gray ranges verified via CSVs; worldwide ranges require aerotransport.org inspection

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable — no external APIs, internal patterns only; ICAO24 allocations change rarely)
