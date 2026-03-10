# Shadow Express: Mapping Iran's Covert Aerial Supply Chain to Syria

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 4 new cubes (dark_flight_detector, set_operations, network_graph_builder, temporal_heatmap), then assemble an 11-cube workflow that answers: *"Can we identify and map a covert Iranian aerial logistics network supplying Syria by cross-correlating aircraft registration, transponder anomalies, dark flight periods, and temporal activity signatures?"*

**Architecture:** The workflow has 3 stages: (1) Identity & Collection — pull Iranian-registered aircraft and Middle East flights, (2) Multi-Dimensional Anomaly Detection — signal health, dark periods, and spatial filtering to converge on a high-confidence suspicious set, (3) Network & Pattern Analysis — build the logistics graph, extract temporal patterns, and visualize. Four new cubes are needed from the planned-cubes spec (Tiers 1 & 3).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pandas, networkx (new dependency), Shapely, existing BaseCube framework.

---

## Why This Can't Be Answered Without The System

An intelligence analyst trying to answer "Is Iran running a covert air bridge to Syria?" faces:

1. **Scale** — Thousands of flights per day in the Middle East. Manual screening is impossible.
2. **Multi-dimensional correlation** — A suspicious flight must fail MULTIPLE checks (Iranian registration + dark transponder periods + GPS jamming signature + Syria corridor transit). No single data point is conclusive. The system intersects all dimensions automatically.
3. **Network invisibility** — Individual flights look innocent. Only when you aggregate airport-to-airport connections and frequency does the logistics NETWORK emerge. A human can't hold 500 flights in working memory.
4. **Temporal signatures** — Covert logistics flights tend to operate at specific times (night, weekends). Detecting this pattern requires statistical analysis across weeks of data.
5. **GPS jamming noise** — Syria has pervasive GPS interference from multiple actors. Separating deliberate jamming (to hide a flight) from environmental jamming requires cross-referencing with transponder behavior — the signal_health_analyzer + dark_flight_detector combination.

---

## Workflow Architecture

```
                    ┌─────────────────────┐
                    │   AlisonFlights      │  ← 30-day window, Middle East bbox
                    │   (Data Source)       │
                    └──────────┬───────────┘
                               │ hex_list
                               ▼
                    ┌─────────────────────┐
                    │ RegCountryFilter     │  ← include: ["Iran", "Syria"]
                    │ (Filter)             │
                    └──────────┬───────────┘
                               │ hex_list (Iranian/Syrian aircraft)
                    ┌──────────┼───────────────────────┐
                    │          │                        │
                    ▼          ▼                        ▼
         ┌──────────────┐ ┌──────────────┐  ┌──────────────────┐
         │ SignalHealth  │ │ DarkFlight   │  │ AreaSpatial      │
         │ Analyzer      │ │ Detector     │  │ Filter           │
         │ (Analysis)    │ │ (Analysis)   │  │ (Filter)         │
         │ NEW CUBE      │ │ NEW CUBE     │  │ Syria polygon    │
         └──────┬───────┘ └──────┬───────┘  └────────┬─────────┘
                │ flight_ids      │ flight_ids         │ flight_ids
                │ (jamming/       │ (dark periods)     │ (Syria transit)
                │  spoofing)      │                    │
                └────────┐       │        ┌───────────┘
                         ▼       ▼        ▼
                    ┌─────────────────────┐
                    │   SetOperations      │  ← intersection of all 3 sets
                    │   (Filter) NEW CUBE  │
                    └──────────┬───────────┘
                               │ result (high-confidence suspicious set)
                    ┌──────────┼──────────────────┐
                    │          │                   │
                    ▼          ▼                   ▼
         ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
         │ GetFlight    │ │ NetworkGraph │ │ Temporal     │
         │ Course       │ │ Builder      │ │ Heatmap      │
         │ (DataSource) │ │ NEW CUBE     │ │ NEW CUBE     │
         └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                │ tracks          │ graph           │ heatmap
                ▼                 ▼                 ▼
         ┌──────────────┐
         │ GeoTemporal  │  ← animated flight tracks
         │ Playback     │
         │ (Output)     │
         └──────────────┘
```

### Cube Inventory

| # | Cube | Status | Role in Workflow |
|---|------|--------|-----------------|
| 1 | `alison_flights` | EXISTS | Collect all aircraft seen in Middle East bbox, 30-day window |
| 2 | `registration_country_filter` | EXISTS | Filter to Iranian/Syrian-registered aircraft |
| 3 | `signal_health_analyzer` | EXISTS | Detect GPS jamming/spoofing events on filtered set |
| 4 | `dark_flight_detector` | **BUILD** | Detect transponder gap periods (dark flights) |
| 5 | `area_spatial_filter` | EXISTS | Filter to flights transiting Syria corridor polygon |
| 6 | `set_operations` | **BUILD** | Intersect anomalous + dark + Syria-transit = suspicious set |
| 7 | `get_flight_course` | EXISTS | Get full track geometry for suspicious flights |
| 8 | `network_graph_builder` | **BUILD** | Build airport-to-airport logistics network graph |
| 9 | `temporal_heatmap` | **BUILD** | Extract time-of-day/day-of-week activity patterns |
| 10 | `geo_temporal_playback` | EXISTS | Animated map visualization of tracks |

---

## Task 1: Build `dark_flight_detector` Cube

**Reference spec:** `.planning/new-cubes/02-behavioral-analysis.md` — Dark Flight Detector section

**Files:**
- Create: `backend/app/cubes/dark_flight_detector.py`
- Test: `backend/tests/test_dark_flight_detector.py`

This cube detects gaps in transponder transmission — periods where an aircraft "goes dark." It queries the `public.positions` table (Alison provider) and the `public.coverage_grid` table to distinguish genuine transponder shutdowns from coverage holes.

### Step 1: Write the failing test

```python
# backend/tests/test_dark_flight_detector.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.cubes.dark_flight_detector import DarkFlightDetectorCube


@pytest.fixture
def cube():
    return DarkFlightDetectorCube()


def test_cube_metadata(cube):
    defn = cube.definition
    assert defn.id == "dark_flight_detector"
    assert defn.category.value == "analysis"
    assert any(p.name == "hex_list" for p in defn.inputs)
    assert any(p.name == "flight_ids" for p in defn.outputs)
    assert any(p.name == "gap_events" for p in defn.outputs)


@pytest.mark.asyncio
async def test_detects_transponder_gap(cube):
    """A 30-minute gap in positions should be detected as a dark flight event."""
    # Mock positions: aircraft seen at T=0, then T=1800 (30 min gap), then T=3600
    mock_positions = [
        {"hex": "4b1234", "ts": "2026-03-01T10:00:00", "lat": 33.5, "lon": 36.3, "alt_baro": 35000},
        {"hex": "4b1234", "ts": "2026-03-01T10:30:00", "lat": 34.0, "lon": 37.0, "alt_baro": 35000},
        {"hex": "4b1234", "ts": "2026-03-01T11:00:00", "lat": 34.5, "lon": 37.5, "alt_baro": 35000},
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock, return_value=mock_positions):
        with patch.object(cube, "_query_coverage_baseline", new_callable=AsyncMock, return_value={}):
            result = await cube.execute(
                hex_list=["4b1234"],
                min_gap_minutes=15,
                lookback_hours=24,
            )

    assert "4b1234" in result["flight_ids"]
    assert len(result["gap_events"]) >= 1
    event = result["gap_events"][0]
    assert event["hex"] == "4b1234"
    assert event["gap_minutes"] >= 15
    assert "start_ts" in event
    assert "end_ts" in event


@pytest.mark.asyncio
async def test_no_gaps_below_threshold(cube):
    """Positions 5 minutes apart should NOT trigger with min_gap=15."""
    mock_positions = [
        {"hex": "4b1234", "ts": "2026-03-01T10:00:00", "lat": 33.5, "lon": 36.3, "alt_baro": 35000},
        {"hex": "4b1234", "ts": "2026-03-01T10:05:00", "lat": 33.6, "lon": 36.4, "alt_baro": 35000},
        {"hex": "4b1234", "ts": "2026-03-01T10:10:00", "lat": 33.7, "lon": 36.5, "alt_baro": 35000},
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock, return_value=mock_positions):
        with patch.object(cube, "_query_coverage_baseline", new_callable=AsyncMock, return_value={}):
            result = await cube.execute(
                hex_list=["4b1234"],
                min_gap_minutes=15,
                lookback_hours=24,
            )

    assert result["flight_ids"] == []
    assert result["gap_events"] == []


@pytest.mark.asyncio
async def test_suspicion_score_higher_for_mid_flight_gap(cube):
    """A gap while airborne (alt > 1000ft) should score higher suspicion."""
    mock_positions = [
        {"hex": "4b1234", "ts": "2026-03-01T10:00:00", "lat": 33.5, "lon": 36.3, "alt_baro": 35000},
        # 45-minute gap while at cruise altitude
        {"hex": "4b1234", "ts": "2026-03-01T10:45:00", "lat": 34.5, "lon": 37.5, "alt_baro": 34000},
    ]

    with patch.object(cube, "_query_positions", new_callable=AsyncMock, return_value=mock_positions):
        with patch.object(cube, "_query_coverage_baseline", new_callable=AsyncMock, return_value={}):
            result = await cube.execute(
                hex_list=["4b1234"],
                min_gap_minutes=15,
                lookback_hours=24,
            )

    assert len(result["gap_events"]) == 1
    event = result["gap_events"][0]
    assert event["suspicion_score"] > 0.5  # airborne gap = higher suspicion
```

### Step 2: Run test to verify it fails

Run: `cd backend && uv run pytest tests/test_dark_flight_detector.py -v`
Expected: FAIL — module `app.cubes.dark_flight_detector` not found

### Step 3: Write the implementation

```python
# backend/app/cubes/dark_flight_detector.py
"""
Dark Flight Detector — finds transponder transmission gaps.

Queries public.positions for an aircraft's position timeline,
identifies gaps exceeding min_gap_minutes, and scores each gap
for suspicion based on altitude context (airborne vs ground)
and coverage baseline.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.cubes.base import BaseCube
from app.database import async_session
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class DarkFlightDetectorCube(BaseCube):
    cube_id = "dark_flight_detector"
    name = "Dark Flight Detector"
    description = (
        "Detects transponder transmission gaps (dark flights) — periods where "
        "an aircraft stops broadcasting ADS-B. Scores each gap for suspicion "
        "based on altitude context and coverage baseline."
    )
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="hex_list",
            type=ParamType.LIST_OF_STRINGS,
            description="ICAO24 hex addresses to analyze",
            required=True,
        ),
        ParamDefinition(
            name="full_result",
            type=ParamType.JSON_OBJECT,
            description="Full result from upstream cube",
            required=False,
            accepts_full_result=True,
        ),
        ParamDefinition(
            name="min_gap_minutes",
            type=ParamType.NUMBER,
            description="Minimum gap duration to flag (minutes)",
            default=15,
        ),
        ParamDefinition(
            name="lookback_hours",
            type=ParamType.NUMBER,
            description="Time window to analyze (hours)",
            default=24,
        ),
    ]

    outputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Hex addresses with detected dark periods",
        ),
        ParamDefinition(
            name="gap_events",
            type=ParamType.JSON_OBJECT,
            description="Array of gap event objects with timing and suspicion scores",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of aircraft with dark periods",
        ),
    ]

    async def execute(self, **inputs) -> dict:
        # Resolve hex_list from full_result or direct input
        full = inputs.get("full_result")
        hex_list = inputs.get("hex_list")
        if not hex_list and full:
            hex_list = full.get("hex_list", [])
        if not hex_list:
            return {"flight_ids": [], "gap_events": [], "count": 0}

        min_gap = float(inputs.get("min_gap_minutes", 15))
        lookback = float(inputs.get("lookback_hours", 24))

        positions = await self._query_positions(hex_list, lookback)
        coverage = await self._query_coverage_baseline(hex_list, lookback)

        # Group positions by hex, sorted by timestamp
        by_hex: dict[str, list] = {}
        for pos in positions:
            h = pos["hex"]
            by_hex.setdefault(h, []).append(pos)

        gap_events = []
        flagged_hexes = set()

        for hex_addr, pos_list in by_hex.items():
            # Sort by timestamp
            pos_list.sort(key=lambda p: p["ts"])
            for i in range(1, len(pos_list)):
                prev = pos_list[i - 1]
                curr = pos_list[i]
                t_prev = self._parse_ts(prev["ts"])
                t_curr = self._parse_ts(curr["ts"])
                gap_minutes = (t_curr - t_prev).total_seconds() / 60.0

                if gap_minutes >= min_gap:
                    # Score suspicion: airborne gaps are more suspicious
                    alt_before = float(prev.get("alt_baro") or 0)
                    alt_after = float(curr.get("alt_baro") or 0)
                    airborne = alt_before > 1000 or alt_after > 1000
                    # Base score from gap duration (longer = more suspicious)
                    duration_score = min(gap_minutes / 120.0, 1.0)
                    altitude_score = 0.4 if airborne else 0.0
                    suspicion = min(duration_score + altitude_score, 1.0)

                    gap_events.append({
                        "hex": hex_addr,
                        "start_ts": prev["ts"],
                        "end_ts": curr["ts"],
                        "gap_minutes": round(gap_minutes, 1),
                        "alt_before_ft": alt_before,
                        "alt_after_ft": alt_after,
                        "airborne": airborne,
                        "suspicion_score": round(suspicion, 3),
                        "lat_before": prev.get("lat"),
                        "lon_before": prev.get("lon"),
                        "lat_after": curr.get("lat"),
                        "lon_after": curr.get("lon"),
                    })
                    flagged_hexes.add(hex_addr)

        # Sort by suspicion descending
        gap_events.sort(key=lambda e: e["suspicion_score"], reverse=True)

        return {
            "flight_ids": sorted(flagged_hexes),
            "gap_events": gap_events,
            "count": len(flagged_hexes),
        }

    async def _query_positions(self, hex_list: list[str], lookback_hours: float) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT hex, ts, lat, lon, alt_baro
                    FROM public.positions
                    WHERE hex = ANY(:hexes)
                      AND ts >= :cutoff
                    ORDER BY hex, ts
                    LIMIT 200000
                """),
                {"hexes": hex_list, "cutoff": cutoff},
            )
            return [dict(r._mapping) for r in result.fetchall()]

    async def _query_coverage_baseline(self, hex_list: list[str], lookback_hours: float) -> dict:
        """Query coverage_grid for baseline reception rates (future enhancement)."""
        return {}

    @staticmethod
    def _parse_ts(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if isinstance(ts, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(ts, fmt)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse timestamp: {ts}")
```

### Step 4: Run tests to verify they pass

Run: `cd backend && uv run pytest tests/test_dark_flight_detector.py -v`
Expected: All 4 tests PASS

### Step 5: Commit

```bash
git add backend/app/cubes/dark_flight_detector.py backend/tests/test_dark_flight_detector.py
git commit -m "feat: add dark_flight_detector cube — transponder gap detection"
```

---

## Task 2: Build `set_operations` Cube

**Reference spec:** `.planning/new-cubes/08-advanced-analysis.md` — Set Operations section

**Files:**
- Create: `backend/app/cubes/set_operations.py`
- Test: `backend/tests/test_set_operations.py`

Pure Python set math on LIST_OF_STRINGS parameters. Supports intersection, union, and difference.

### Step 1: Write the failing test

```python
# backend/tests/test_set_operations.py
import pytest
from app.cubes.set_operations import SetOperationsCube


@pytest.fixture
def cube():
    return SetOperationsCube()


def test_cube_metadata(cube):
    defn = cube.definition
    assert defn.id == "set_operations"
    assert defn.category.value == "filter"
    assert any(p.name == "set_a" for p in defn.inputs)
    assert any(p.name == "set_b" for p in defn.inputs)
    assert any(p.name == "set_c" for p in defn.inputs)
    assert any(p.name == "operation" for p in defn.inputs)
    assert any(p.name == "result" for p in defn.outputs)


@pytest.mark.asyncio
async def test_intersection(cube):
    result = await cube.execute(
        set_a=["a", "b", "c", "d"],
        set_b=["b", "c", "e"],
        operation="intersection",
    )
    assert sorted(result["result"]) == ["b", "c"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_union(cube):
    result = await cube.execute(
        set_a=["a", "b"],
        set_b=["b", "c"],
        operation="union",
    )
    assert sorted(result["result"]) == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_difference(cube):
    result = await cube.execute(
        set_a=["a", "b", "c"],
        set_b=["b"],
        operation="difference",
    )
    assert sorted(result["result"]) == ["a", "c"]


@pytest.mark.asyncio
async def test_three_way_intersection(cube):
    result = await cube.execute(
        set_a=["a", "b", "c", "d"],
        set_b=["b", "c", "d", "e"],
        set_c=["c", "d", "e", "f"],
        operation="intersection",
    )
    assert sorted(result["result"]) == ["c", "d"]
```

### Step 2: Run test to verify it fails

Run: `cd backend && uv run pytest tests/test_set_operations.py -v`
Expected: FAIL — module not found

### Step 3: Write the implementation

```python
# backend/app/cubes/set_operations.py
"""
Set Operations — intersection, union, difference on flight ID lists.

Enables combining results from multiple analysis branches.
Supports 2-way or 3-way operations.
"""
from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class SetOperationsCube(BaseCube):
    cube_id = "set_operations"
    name = "Set Operations"
    description = (
        "Performs set operations (intersection, union, difference) on flight ID lists. "
        "Use to combine or filter results from multiple analysis branches."
    )
    category = CubeCategory.FILTER

    inputs = [
        ParamDefinition(
            name="set_a",
            type=ParamType.LIST_OF_STRINGS,
            description="First set of IDs",
            required=True,
        ),
        ParamDefinition(
            name="set_b",
            type=ParamType.LIST_OF_STRINGS,
            description="Second set of IDs",
            required=True,
        ),
        ParamDefinition(
            name="set_c",
            type=ParamType.LIST_OF_STRINGS,
            description="Optional third set of IDs (for 3-way operations)",
            required=False,
        ),
        ParamDefinition(
            name="operation",
            type=ParamType.STRING,
            description="Operation: intersection, union, or difference (A minus B)",
            default="intersection",
            widget_hint="select",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="result",
            type=ParamType.LIST_OF_STRINGS,
            description="Resulting set of IDs",
        ),
        ParamDefinition(
            name="count",
            type=ParamType.NUMBER,
            description="Number of IDs in result",
        ),
    ]

    async def execute(self, **inputs) -> dict:
        a = set(inputs.get("set_a") or [])
        b = set(inputs.get("set_b") or [])
        c_raw = inputs.get("set_c")
        c = set(c_raw) if c_raw else None

        op = (inputs.get("operation") or "intersection").lower().strip()

        if op == "intersection":
            result = a & b
            if c is not None:
                result = result & c
        elif op == "union":
            result = a | b
            if c is not None:
                result = result | c
        elif op == "difference":
            result = a - b
            if c is not None:
                result = result - c
        else:
            raise ValueError(f"Unknown operation: {op}. Use intersection, union, or difference.")

        sorted_result = sorted(result)
        return {"result": sorted_result, "count": len(sorted_result)}
```

### Step 4: Run tests

Run: `cd backend && uv run pytest tests/test_set_operations.py -v`
Expected: All 5 tests PASS

### Step 5: Commit

```bash
git add backend/app/cubes/set_operations.py backend/tests/test_set_operations.py
git commit -m "feat: add set_operations cube — intersection, union, difference on ID lists"
```

---

## Task 3: Build `network_graph_builder` Cube

**Reference spec:** `.planning/new-cubes/08-advanced-analysis.md` — Network Graph Builder section

**Files:**
- Create: `backend/app/cubes/network_graph_builder.py`
- Test: `backend/tests/test_network_graph_builder.py`

Builds an airport-to-airport network graph from flight metadata. Uses pandas for aggregation and networkx for graph metrics.

### Step 1: Add networkx dependency

Run: `cd backend && uv add networkx`

### Step 2: Write the failing test

```python
# backend/tests/test_network_graph_builder.py
import pytest
from app.cubes.network_graph_builder import NetworkGraphBuilderCube


@pytest.fixture
def cube():
    return NetworkGraphBuilderCube()


def test_cube_metadata(cube):
    defn = cube.definition
    assert defn.id == "network_graph_builder"
    assert defn.category.value == "analysis"


@pytest.mark.asyncio
async def test_builds_route_graph(cube):
    flights = [
        {"flight_id": "f1", "origin_airport": "OIIE", "destination_airport": "OSDI", "callsign": "IRM001"},
        {"flight_id": "f2", "origin_airport": "OIIE", "destination_airport": "OSDI", "callsign": "IRM002"},
        {"flight_id": "f3", "origin_airport": "OSDI", "destination_airport": "OLBA", "callsign": "SYR01"},
        {"flight_id": "f4", "origin_airport": "OIIE", "destination_airport": "OLBA", "callsign": "IRM003"},
    ]
    result = await cube.execute(
        flights=flights,
        graph_type="route",
        min_edge_weight=1,
    )

    nodes = result["nodes"]
    edges = result["edges"]

    airport_ids = [n["id"] for n in nodes]
    assert "OIIE" in airport_ids  # Tehran
    assert "OSDI" in airport_ids  # Damascus
    assert "OLBA" in airport_ids  # Beirut

    # OIIE -> OSDI should have weight 2 (two flights)
    oiie_osdi = [e for e in edges if e["source"] == "OIIE" and e["target"] == "OSDI"]
    assert len(oiie_osdi) == 1
    assert oiie_osdi[0]["weight"] == 2

    assert result["stats"]["total_nodes"] == 3
    assert result["stats"]["total_edges"] == 3


@pytest.mark.asyncio
async def test_min_edge_weight_filter(cube):
    flights = [
        {"flight_id": "f1", "origin_airport": "OIIE", "destination_airport": "OSDI", "callsign": "IRM001"},
        {"flight_id": "f2", "origin_airport": "OIIE", "destination_airport": "OSDI", "callsign": "IRM002"},
        {"flight_id": "f3", "origin_airport": "OSDI", "destination_airport": "OLBA", "callsign": "SYR01"},
    ]
    result = await cube.execute(
        flights=flights,
        graph_type="route",
        min_edge_weight=2,  # only OIIE->OSDI qualifies
    )
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "OIIE"


@pytest.mark.asyncio
async def test_centrality_scores(cube):
    flights = [
        {"flight_id": "f1", "origin_airport": "OIIE", "destination_airport": "OSDI"},
        {"flight_id": "f2", "origin_airport": "OSDI", "destination_airport": "OLBA"},
        {"flight_id": "f3", "origin_airport": "OSDI", "destination_airport": "OIIE"},
        {"flight_id": "f4", "origin_airport": "OLBA", "destination_airport": "OSDI"},
    ]
    result = await cube.execute(flights=flights, graph_type="route", min_edge_weight=1)

    # OSDI (Damascus) should be most central — it's the hub
    osdi_node = [n for n in result["nodes"] if n["id"] == "OSDI"][0]
    oiie_node = [n for n in result["nodes"] if n["id"] == "OIIE"][0]
    assert osdi_node["degree_centrality"] >= oiie_node["degree_centrality"]
```

### Step 3: Run test to verify it fails

Run: `cd backend && uv run pytest tests/test_network_graph_builder.py -v`
Expected: FAIL — module not found

### Step 4: Write the implementation

```python
# backend/app/cubes/network_graph_builder.py
"""
Network Graph Builder — builds airport-to-airport logistics network.

Takes flight metadata and constructs a directed graph where nodes are
airports and edges are routes weighted by flight frequency. Computes
centrality metrics to identify hub airports.
"""
import networkx as nx

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class NetworkGraphBuilderCube(BaseCube):
    cube_id = "network_graph_builder"
    name = "Network Graph Builder"
    description = (
        "Builds a directed network graph from flight data. Nodes are airports, "
        "edges are routes weighted by flight frequency. Identifies hub airports "
        "via centrality metrics."
    )
    category = CubeCategory.ANALYSIS

    inputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            description="Array of flight objects with origin_airport and destination_airport",
            required=True,
            accepts_full_result=True,
        ),
        ParamDefinition(
            name="graph_type",
            type=ParamType.STRING,
            description="Graph type: 'route' (airport-to-airport)",
            default="route",
            widget_hint="select",
        ),
        ParamDefinition(
            name="min_edge_weight",
            type=ParamType.NUMBER,
            description="Minimum flight count to include an edge",
            default=1,
        ),
    ]

    outputs = [
        ParamDefinition(
            name="nodes",
            type=ParamType.JSON_OBJECT,
            description="Array of node objects with centrality metrics",
        ),
        ParamDefinition(
            name="edges",
            type=ParamType.JSON_OBJECT,
            description="Array of edge objects with weight and callsigns",
        ),
        ParamDefinition(
            name="stats",
            type=ParamType.JSON_OBJECT,
            description="Graph statistics (total nodes, edges, density)",
        ),
    ]

    async def execute(self, **inputs) -> dict:
        raw = inputs.get("flights") or []
        # Handle full_result wrapping
        if isinstance(raw, dict):
            raw = raw.get("flights", raw.get("filtered_flights", []))

        min_weight = int(inputs.get("min_edge_weight", 1))

        # Build edge counts
        edge_counts: dict[tuple[str, str], dict] = {}
        for flight in raw:
            origin = flight.get("origin_airport")
            dest = flight.get("destination_airport")
            if not origin or not dest:
                continue
            key = (origin, dest)
            if key not in edge_counts:
                edge_counts[key] = {"weight": 0, "callsigns": set(), "flight_ids": []}
            edge_counts[key]["weight"] += 1
            cs = flight.get("callsign")
            if cs:
                edge_counts[key]["callsigns"].add(cs)
            fid = flight.get("flight_id")
            if fid:
                edge_counts[key]["flight_ids"].append(fid)

        # Build networkx graph (filtered by min weight)
        G = nx.DiGraph()
        for (src, dst), data in edge_counts.items():
            if data["weight"] >= min_weight:
                G.add_edge(src, dst, weight=data["weight"])

        # Compute centrality
        degree_cent = nx.degree_centrality(G) if len(G) > 0 else {}
        betweenness = nx.betweenness_centrality(G, weight="weight") if len(G) > 1 else {}

        nodes = []
        for node in G.nodes():
            nodes.append({
                "id": node,
                "degree_centrality": round(degree_cent.get(node, 0), 4),
                "betweenness_centrality": round(betweenness.get(node, 0), 4),
                "in_degree": G.in_degree(node),
                "out_degree": G.out_degree(node),
            })
        nodes.sort(key=lambda n: n["degree_centrality"], reverse=True)

        edges = []
        for (src, dst), data in edge_counts.items():
            if data["weight"] >= min_weight:
                edges.append({
                    "source": src,
                    "target": dst,
                    "weight": data["weight"],
                    "callsigns": sorted(data["callsigns"]),
                    "flight_ids": data["flight_ids"],
                })
        edges.sort(key=lambda e: e["weight"], reverse=True)

        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "density": round(nx.density(G), 4) if len(G) > 0 else 0,
        }

        return {"nodes": nodes, "edges": edges, "stats": stats}
```

### Step 5: Run tests

Run: `cd backend && uv run pytest tests/test_network_graph_builder.py -v`
Expected: All 4 tests PASS

### Step 6: Commit

```bash
git add backend/app/cubes/network_graph_builder.py backend/tests/test_network_graph_builder.py
git commit -m "feat: add network_graph_builder cube — airport logistics network with centrality"
```

---

## Task 4: Build `temporal_heatmap` Cube

**Reference spec:** `.planning/new-cubes/08-advanced-analysis.md` — Temporal Heatmap section

**Files:**
- Create: `backend/app/cubes/temporal_heatmap.py`
- Test: `backend/tests/test_temporal_heatmap.py`

Aggregates flight activity by time buckets (hour-of-day, day-of-week) to reveal operational tempo patterns.

### Step 1: Write the failing test

```python
# backend/tests/test_temporal_heatmap.py
import pytest
from app.cubes.temporal_heatmap import TemporalHeatmapCube


@pytest.fixture
def cube():
    return TemporalHeatmapCube()


def test_cube_metadata(cube):
    defn = cube.definition
    assert defn.id == "temporal_heatmap"
    assert defn.category.value == "aggregation"


@pytest.mark.asyncio
async def test_hourly_buckets(cube):
    flights = [
        {"flight_id": "f1", "first_seen_ts": 1709251200},  # 2024-03-01 00:00 UTC (Friday)
        {"flight_id": "f2", "first_seen_ts": 1709254800},  # 2024-03-01 01:00 UTC
        {"flight_id": "f3", "first_seen_ts": 1709251200},  # 2024-03-01 00:00 UTC (same hour)
        {"flight_id": "f4", "first_seen_ts": 1709337600},  # 2024-03-02 00:00 UTC (Saturday)
    ]
    result = await cube.execute(flights=flights, granularity="hourly")

    buckets = result["buckets"]
    assert len(buckets) > 0
    # Hour 0 should have 3 flights (f1, f3, f4)
    hour_0 = [b for b in buckets if b["hour"] == 0]
    assert len(hour_0) == 1
    assert hour_0[0]["count"] == 3


@pytest.mark.asyncio
async def test_day_of_week_buckets(cube):
    flights = [
        {"flight_id": "f1", "first_seen_ts": 1709251200},  # Friday
        {"flight_id": "f2", "first_seen_ts": 1709337600},  # Saturday
        {"flight_id": "f3", "first_seen_ts": 1709337600},  # Saturday
    ]
    result = await cube.execute(flights=flights, granularity="daily")

    buckets = result["buckets"]
    sat_bucket = [b for b in buckets if b["day_name"] == "Saturday"]
    assert len(sat_bucket) == 1
    assert sat_bucket[0]["count"] == 2


@pytest.mark.asyncio
async def test_peak_detection(cube):
    # Create data with a clear spike at hour 2
    flights = [{"flight_id": f"f{i}", "first_seen_ts": 1709258400} for i in range(10)]  # hour 2: 10 flights
    flights += [{"flight_id": "fx", "first_seen_ts": 1709251200}]  # hour 0: 1 flight

    result = await cube.execute(flights=flights, granularity="hourly")
    assert result["peak"]["hour"] == 2
    assert result["peak"]["count"] == 10
```

### Step 2: Run test to verify it fails

Run: `cd backend && uv run pytest tests/test_temporal_heatmap.py -v`
Expected: FAIL — module not found

### Step 3: Write the implementation

```python
# backend/app/cubes/temporal_heatmap.py
"""
Temporal Heatmap — aggregates flight activity by time buckets.

Reveals operational tempo patterns: hour-of-day, day-of-week.
Identifies peak activity periods for pattern-of-life analysis.
"""
from datetime import datetime, timezone

from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TemporalHeatmapCube(BaseCube):
    cube_id = "temporal_heatmap"
    name = "Temporal Heatmap"
    description = (
        "Aggregates flight activity by time buckets (hour-of-day, day-of-week) "
        "to reveal operational tempo patterns. Identifies peak activity periods."
    )
    category = CubeCategory.AGGREGATION

    inputs = [
        ParamDefinition(
            name="flights",
            type=ParamType.JSON_OBJECT,
            description="Array of flight objects with first_seen_ts (epoch seconds)",
            required=True,
            accepts_full_result=True,
        ),
        ParamDefinition(
            name="granularity",
            type=ParamType.STRING,
            description="Bucket type: 'hourly' (hour of day) or 'daily' (day of week)",
            default="hourly",
            widget_hint="select",
        ),
    ]

    outputs = [
        ParamDefinition(
            name="buckets",
            type=ParamType.JSON_OBJECT,
            description="Array of time bucket objects with counts",
        ),
        ParamDefinition(
            name="peak",
            type=ParamType.JSON_OBJECT,
            description="The bucket with highest activity",
        ),
        ParamDefinition(
            name="total_flights",
            type=ParamType.NUMBER,
            description="Total flights analyzed",
        ),
    ]

    async def execute(self, **inputs) -> dict:
        raw = inputs.get("flights") or []
        if isinstance(raw, dict):
            raw = raw.get("flights", raw.get("filtered_flights", []))

        granularity = (inputs.get("granularity") or "hourly").lower().strip()

        # Parse timestamps
        datetimes = []
        for f in raw:
            ts = f.get("first_seen_ts")
            if ts is None:
                continue
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            datetimes.append(dt)

        if not datetimes:
            return {"buckets": [], "peak": {}, "total_flights": 0}

        if granularity == "hourly":
            buckets = self._hourly_buckets(datetimes)
        else:
            buckets = self._daily_buckets(datetimes)

        peak = max(buckets, key=lambda b: b["count"]) if buckets else {}

        return {
            "buckets": buckets,
            "peak": peak,
            "total_flights": len(datetimes),
        }

    @staticmethod
    def _hourly_buckets(datetimes: list[datetime]) -> list[dict]:
        counts = [0] * 24
        for dt in datetimes:
            counts[dt.hour] += 1
        return [{"hour": h, "count": c} for h, c in enumerate(counts) if c > 0]

    @staticmethod
    def _daily_buckets(datetimes: list[datetime]) -> list[dict]:
        counts = [0] * 7
        for dt in datetimes:
            counts[dt.weekday()] += 1
        return [
            {"day": d, "day_name": DAY_NAMES[d], "count": c}
            for d, c in enumerate(counts)
            if c > 0
        ]
```

### Step 4: Run tests

Run: `cd backend && uv run pytest tests/test_temporal_heatmap.py -v`
Expected: All 4 tests PASS

### Step 5: Commit

```bash
git add backend/app/cubes/temporal_heatmap.py backend/tests/test_temporal_heatmap.py
git commit -m "feat: add temporal_heatmap cube — time-of-day/day-of-week activity patterns"
```

---

## Task 5: Assemble the "Shadow Express" Workflow

Now that all 4 new cubes exist, configure the workflow in the UI.

### Step 1: Document the workflow configuration

This step is manual — create the workflow in the Tracer 12-flow UI. Below is the exact configuration for each node and connection.

**Workflow Name:** `Shadow Express — Iran Aerial Logistics to Syria`

#### Node 1: Alison Flights (Data Source)
- **Cube:** `alison_flights`
- **Parameters:**
  - `time_range_seconds`: `2592000` (30 days)
  - `polygon`: `[[29.0, 32.0], [29.0, 52.0], [38.0, 52.0], [38.0, 32.0]]` (Middle East bbox: covers Iraq, Syria, Lebanon, Iran)
- **Position:** top-center

#### Node 2: Registration Country Filter
- **Cube:** `registration_country_filter`
- **Parameters:**
  - `filter_mode`: `include`
  - `countries`: `["Iran", "Syria"]`
- **Connection IN:** Node 1 `hex_list` → Node 2 `hex_list`

#### Node 3: Signal Health Analyzer (Branch A — Jamming/Spoofing)
- **Cube:** `signal_health_analyzer`
- **Parameters:**
  - `classify_mode`: `["Jamming", "Spoofing"]`
  - `target_phase`: `cruise`
- **Connection IN:** Node 2 `hex_list` → Node 3 `hex_list`

#### Node 4: Dark Flight Detector (Branch B — Transponder Gaps)
- **Cube:** `dark_flight_detector`
- **Parameters:**
  - `min_gap_minutes`: `20`
  - `lookback_hours`: `720` (30 days)
- **Connection IN:** Node 2 `hex_list` → Node 4 `hex_list`

#### Node 5: Area Spatial Filter (Branch C — Syria Corridor)
- **Cube:** `area_spatial_filter`
- **Parameters:**
  - `provider`: `alison`
  - `polygon`: `[[33.0, 35.5], [33.0, 42.5], [37.5, 42.5], [37.5, 35.5]]` (Syria + Lebanon corridor)
  - `time_window_hours`: `720`
- **Connection IN:** Node 2 `hex_list` → Node 5 `hex_list`

#### Node 6: Set Operations — Intersect (Convergence)
- **Cube:** `set_operations`
- **Parameters:**
  - `operation`: `intersection`
- **Connections IN:**
  - Node 3 `flight_ids` → Node 6 `set_a` (jamming/spoofing aircraft)
  - Node 4 `flight_ids` → Node 6 `set_b` (dark flight aircraft)
  - Node 5 `flight_ids` → Node 6 `set_c` (Syria corridor aircraft)
- **Output:** The intersection = aircraft that are Iranian-registered AND show jamming/spoofing AND have dark periods AND fly through Syria. **This is the high-confidence suspicious set.**

#### Node 7: Get Flight Course (Tracks)
- **Cube:** `get_flight_course`
- **Parameters:**
  - `output_mode`: `lines`
- **Connection IN:** Node 6 `result` → Node 7 `flight_ids`
- **Note:** This cube uses FR provider (research.normal_tracks). The hex addresses from Alison may not directly match FR flight_ids. If this doesn't work, we can add AllFlights as an intermediate step with hex→callsign resolution.

#### Node 8: Network Graph Builder
- **Cube:** `network_graph_builder`
- **Parameters:**
  - `graph_type`: `route`
  - `min_edge_weight`: `2` (routes used at least twice)
- **Connection IN:** Node 1 `__full_result__` → Node 8 `flights` (uses full Alison dataset filtered through the suspicious set)
- **Alternative:** If we need only suspicious flights' routes, wire Node 6 `result` to an AllFlights cube that resolves hex→flight metadata, then feed to Node 8.

#### Node 9: Temporal Heatmap
- **Cube:** `temporal_heatmap`
- **Parameters:**
  - `granularity`: `hourly`
- **Connection IN:** Feed from filtered flights metadata into this cube
- **Purpose:** Reveals if suspicious flights operate at specific hours (night flights = higher suspicion for covert ops)

#### Node 10: Geo-Temporal Playback (Visualization)
- **Cube:** `geo_temporal_playback`
- **Parameters:**
  - `geometry_column`: `geometry`
  - `timestamp_column`: `timestamp`
  - `id_column`: `flight_id`
- **Connection IN:** Node 7 `tracks` → Node 10 `data`

### Step 2: Create the workflow via API (optional — can also do in UI)

```bash
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Shadow Express — Iran Aerial Logistics to Syria"}'
```

Then open the workflow in the UI and drag/configure each node as documented above.

### Step 3: Commit workflow documentation

```bash
git add docs/plans/2026-03-09-shadow-express-iran-logistics-workflow.md
git commit -m "docs: Shadow Express workflow plan — Iran aerial logistics detection"
```

---

## Expected Analytical Outcomes

When this workflow executes successfully, the analyst should see:

1. **Set Operations result:** A list of 0-N Iranian/Syrian aircraft hex addresses that simultaneously:
   - Show GPS jamming or spoofing signatures (signal manipulation)
   - Have transponder dark periods > 20 minutes while airborne
   - Were detected transiting the Syria/Lebanon corridor

2. **Network Graph:** An airport-to-airport directed graph revealing:
   - Hub airports (high centrality = likely logistics hubs, e.g. Damascus OSDI, Tehran OIIE)
   - Route frequency (thick edges = regular supply routes)
   - Which callsigns operate each route

3. **Temporal Heatmap:** Activity patterns showing:
   - Peak hours (night flights suggest covert operations)
   - Day-of-week patterns (regular schedule suggests organized logistics vs ad-hoc)

4. **Geo-Temporal Playback:** Animated map showing:
   - Flight tracks of suspicious aircraft over time
   - Visual identification of the corridor pattern
   - Convergence on specific airports

## Interpretation Guide

| Finding | Intelligence Assessment |
|---------|----------------------|
| Intersection set is empty | No aircraft match ALL criteria — relax filters (try union instead of intersection, or lower min_gap) |
| 1-5 aircraft in intersection | Strong leads — investigate each individually. Cross-reference callsigns with known operators. |
| Network shows OIIE↔OSDI as strongest edge | Tehran-Damascus axis confirmed as primary supply route |
| Peak activity at 01:00-04:00 UTC | Night operations consistent with covert logistics |
| Regular weekly pattern (e.g., every Tuesday/Thursday) | Scheduled logistics rotation — very high confidence of organized supply chain |
| Dark periods cluster over specific geography | Deliberate transponder shutoff over sensitive areas (e.g., eastern Syria, near conflict zones) |

---

## Adjustments & Fallbacks

- **If intersection is too narrow:** Replace `set_operations` with `union` mode, or remove one branch (e.g., drop jamming requirement, keep only dark + Syria).
- **If hex→flight_id mismatch:** The Alison provider uses hex addresses while FR uses flight_ids. Add an intermediate `all_flights` cube that queries by callsign to bridge the gap.
- **If 30-day window is too heavy:** Reduce `time_range_seconds` to 7 days (604800) for faster iteration.
- **Network graph empty:** Lower `min_edge_weight` to 1 to include all routes.
