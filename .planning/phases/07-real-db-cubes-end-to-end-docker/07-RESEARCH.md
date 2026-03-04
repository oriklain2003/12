# Phase 7: Real DB Cubes, End-to-End & Docker - Research

**Researched:** 2026-03-04
**Domain:** SQLAlchemy async queries, pandas groupby, React-Leaflet polygon drawing, Docker multi-stage builds (uv + nginx)
**Confidence:** HIGH

## Summary

Phase 7 finishes the application by wiring real Tracer 42 data through production cubes, adding a polygon map widget for geofence input, and packaging everything into Docker containers. The backend work is mostly additive — two new cube files auto-discover into the existing registry, plus enhancements to `all_flights.py`. The frontend adds one new `widget_hint` type (`polygon`) that opens a Leaflet map overlay for drawing geofences. Docker uses well-established multi-stage patterns: `uv sync --frozen` in builder stage, slim Python runtime for backend; `pnpm build` in builder, nginx for SPA serving.

The biggest unknowns going in were the actual DB schema (now confirmed) and whether `country`/`region` columns exist in `research.flight_metadata`. They do NOT — there are no country or region columns in `flight_metadata`. Country/region filtering in the CONTEXT.md must be implemented via bounding-box lat/lon ranges (which do exist: `start_lat`, `start_lon`, `end_lat`, `end_lon`, `origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`). The polygon filter already covers geofence filtering; "region" can be a named bounding-box preset or just dropped. The `airline` column DOES exist and is the natural group-by field for Count By Field demos.

`pandas` is not in backend dependencies and must be added via `uv add pandas` before the Count By Field cube can use it.

**Primary recommendation:** Implement in this order: (1) enhance AllFlights, (2) add GetAnomalies cube, (3) add CountByField cube with pandas, (4) add polygon widget to frontend, (5) write Dockerfiles and docker-compose. The polygon widget is the riskiest frontend piece — use React-Leaflet's existing event system (`useMapEvents`) rather than any third-party drawing library.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- No new Get Flights or Filter Flights cubes — enhance existing `AllFlightsCube` in `all_flights.py` (DATA-01 and DATA-02 merged)
- AllFlights: add more filter options (airport, region, country) alongside existing filters; accept both absolute dates and relative time
- Keep current AllFlights output fields: flight_id, callsign, first_seen_ts, last_seen_ts, min/max_altitude_ft, origin/destination_airport, is_anomaly, is_military, start/end_lat/lon
- Polygon map widget: `widget_hint: "polygon"` opens a map overlay; user clicks to place polygon points forming a geofence; coordinates sent as JSON array of [lat, lon] pairs
- Get Anomalies cube: queries `research.anomaly_reports` for given flight_ids; accepts flight_ids array as input; returns anomaly records with severity and report data
- Count By Field cube: pure Python using pandas DataFrame groupby; accepts any data array + `group_by_field` name; outputs array of `{value, count}` objects; single group field only
- Docker: multi-stage backend (uv sync → slim Python), multi-stage frontend (pnpm build → nginx SPA), docker-compose with .env

### Claude's Discretion
- Additional filter options to add to AllFlights (airport ILIKE, country, region bounding box)
- Get Anomalies output columns and filter options
- Polygon map widget UX details (close behavior, point editing, visual style)
- Docker health checks, port mapping, container naming
- nginx configuration details
- pandas vs manual Python for Count By Field (pandas preferred but Claude can adjust if dependency is unwanted)

### Deferred Ideas (OUT OF SCOPE)
- Polygon drawing/editing UI improvements (vertex dragging, shape presets)
- Additional AllFlights output fields beyond current set
- Multiple group-by fields for Count By Field
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Get Flights cube — time_range, airport, region filters; outputs flight_ids + flights array | Merged into AllFlights enhancement; confirmed DB columns (origin_airport, destination_airport, start/end_lat/lon exist; no country/region column — use lat/lon bounding box for region) |
| DATA-02 | Filter Flights cube — country, days_back, altitude filters | Merged into AllFlights; country filter requires bounding-box approach since no country column exists in flight_metadata |
| DATA-03 | Get Anomalies cube — accepts flight_ids, queries research.anomaly_reports | Schema confirmed: id, flight_id, timestamp, is_anomaly, severity_cnn, severity_dense, full_report, callsign, airline, origin_airport, destination_airport, aircraft_type, geographic_region, is_military, matched_rule_ids, matched_rule_names |
| DATA-04 | Count By Field — any data array + group_by_field, pandas groupby, outputs {field_value, count} | pandas not installed; must add to pyproject.toml; pattern confirmed |
| DATA-05 | End-to-end pipeline: AllFlights → GetAnomalies → CountByField returns real data | DB connectivity confirmed via live schema queries; row limit cap at 100 applies |
| DEPL-01 | docker-compose.yml — backend + frontend services, shared network, .env | No existing docker-compose; DATABASE_URL is in .env at project root; backend config reads `../. env` (relative to backend/) — must adjust for Docker |
| DEPL-02 | Backend Dockerfile — multi-stage, uv for deps, slim Python runtime | uv 0.9.26 available; uv.lock exists in backend/; Python 3.12 in venv |
| DEPL-03 | Frontend Dockerfile — multi-stage, pnpm build, nginx serving SPA with /api proxy | pnpm 10.28.2, node 24; vite builds to dist/; nginx needs SPA fallback + /api proxy |
</phase_requirements>

## Standard Stack

### Core (Backend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy async | 2.0+ (already installed) | DB queries in GetAnomalies | Established pattern from AllFlights cube |
| asyncpg | 0.30+ (already installed) | PostgreSQL async driver | Already wired in database.py |
| pandas | 2.x (NOT YET INSTALLED) | DataFrame groupby for CountByField | User-specified; avoid hand-rolling groupby |
| uv | 0.9.26 | Python deps in Dockerfile | Project standard |

### Core (Frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-leaflet | 5.0.0 (already installed) | Polygon drawing overlay map | Already in package.json — useMapEvents for click capture |
| leaflet | 1.9.4 (already installed) | Underlying map tiles | Already in package.json |

### Core (Docker)
| Tool | Version | Purpose | Why |
|------|---------|---------|-----|
| python:3.12-slim | latest slim | Backend runtime image | Matches dev Python 3.12 |
| nginx:alpine | latest alpine | Frontend static serving + /api proxy | Minimal footprint, SPA-capable |
| node:24-alpine | latest alpine | Frontend build stage | Matches dev node 24 |
| ghcr.io/astral-sh/uv | 0.9.26 (pin) | Backend deps install stage | Official uv Docker image |

### Installation Required
```bash
# Backend — add pandas
cd backend && uv add pandas
```

No new frontend packages needed (react-leaflet already handles polygon drawing via useMapEvents).

## Architecture Patterns

### Recommended File Layout for Phase 7
```
backend/app/cubes/
├── all_flights.py          # Enhance: add airport/region filters + airline/country columns
├── get_anomalies.py        # NEW: queries research.anomaly_reports by flight_ids
├── count_by_field.py       # NEW: pandas groupby aggregation
frontend/src/components/CubeNode/
├── ParamField.tsx          # Add polygon widget_hint branch
├── PolygonMapWidget.tsx    # NEW: Leaflet overlay for geofence drawing
backend/Dockerfile          # NEW
frontend/Dockerfile         # NEW
frontend/nginx.conf         # NEW
docker-compose.yml          # NEW (at project root)
```

### Pattern 1: New Cube — GetAnomalies
**What:** Subclass BaseCube, use `engine.connect()` directly (Phase 02 decision), accept `flight_ids` array, return anomaly records.
**When to use:** Any cube that reads from a single table by ID array.
**Example:**
```python
# Mirrors AllFlights pattern from all_flights.py
from app.cubes.base import BaseCube
from app.database import engine
from sqlalchemy import text

class GetAnomaliesCube(BaseCube):
    cube_id = "get_anomalies"
    name = "Get Anomalies"
    category = CubeCategory.DATA_SOURCE

    inputs = [
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Flight IDs to look up anomaly reports for.",
            required=True,
        ),
        ParamDefinition(
            name="min_severity",
            type=ParamType.NUMBER,
            description="Minimum severity_cnn score (0.0-1.0). Optional.",
            required=False,
        ),
    ]
    outputs = [
        ParamDefinition(
            name="anomalies",
            type=ParamType.JSON_OBJECT,
            description="Array of anomaly report objects.",
        ),
        ParamDefinition(
            name="flight_ids",
            type=ParamType.LIST_OF_STRINGS,
            description="Unique flight_ids that have anomaly records.",
        ),
    ]

    async def execute(self, **inputs):
        flight_ids = inputs.get("flight_ids") or []
        min_severity = inputs.get("min_severity")

        if not flight_ids:
            return {"anomalies": [], "flight_ids": []}

        sql = """
            SELECT id, flight_id, timestamp, is_anomaly, severity_cnn, severity_dense,
                   callsign, airline, origin_airport, destination_airport,
                   aircraft_type, geographic_region, is_military,
                   matched_rule_ids, matched_rule_names
            FROM research.anomaly_reports
            WHERE flight_id = ANY(:flight_ids)
        """
        params = {"flight_ids": list(flight_ids)}

        if min_severity is not None:
            sql += " AND severity_cnn >= :min_severity"
            params["min_severity"] = float(min_severity)

        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

        unique_ids = list({r["flight_id"] for r in rows})
        return {"anomalies": rows, "flight_ids": unique_ids}
```

### Pattern 2: CountByField with pandas
**What:** Pure Python groupby using pandas DataFrame — no DB connection needed.
**When to use:** Aggregation cubes operating on already-fetched row data.
**Example:**
```python
import pandas as pd
from app.cubes.base import BaseCube

class CountByFieldCube(BaseCube):
    cube_id = "count_by_field"
    name = "Count By Field"
    category = CubeCategory.AGGREGATION

    inputs = [
        ParamDefinition(
            name="data",
            type=ParamType.JSON_OBJECT,
            description="Array of row objects to group.",
            required=True,
            accepts_full_result=False,
        ),
        ParamDefinition(
            name="group_by_field",
            type=ParamType.STRING,
            description="Field name to group by (e.g. 'airline', 'origin_airport').",
            required=True,
        ),
    ]
    outputs = [
        ParamDefinition(
            name="counts",
            type=ParamType.JSON_OBJECT,
            description="Array of {value, count} objects sorted by count desc.",
        ),
    ]

    async def execute(self, **inputs):
        data = inputs.get("data") or []
        group_by_field = inputs.get("group_by_field", "")

        if not data or not group_by_field:
            return {"counts": []}

        df = pd.DataFrame(data)
        if group_by_field not in df.columns:
            return {"counts": []}

        grouped = (
            df.groupby(group_by_field, dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        result = [
            {"value": str(row[group_by_field]), "count": int(row["count"])}
            for _, row in grouped.iterrows()
        ]
        return {"counts": result}
```

### Pattern 3: AllFlights Enhancement
**What:** Add `airport`, `country`/`region` (bounding box), and `airline` filter params. Add `airline` and `airline_code` to SELECT columns. Note: no `country` or `region` column in DB — implement "country" filter as bounding-box lat/lon preset or skip; "region" as bounding-box lat/lon range params.
**Key schema facts confirmed from live DB:**
- `flight_metadata` has: `airline`, `airline_code`, `origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`, `start_lat`, `start_lon`, `end_lat`, `end_lon`
- No `country` column, no `region` column
- Airport filter: `origin_airport ILIKE :airport OR destination_airport ILIKE :airport`

```python
# New params to add to AllFlights.inputs:
ParamDefinition(
    name="airport",
    type=ParamType.STRING,
    description="Airport code filter (ILIKE — matches origin or destination).",
    required=False,
),
ParamDefinition(
    name="min_lat",
    type=ParamType.NUMBER,
    description="Region bounding box — minimum latitude.",
    required=False,
),
ParamDefinition(
    name="max_lat",
    type=ParamType.NUMBER,
    description="Region bounding box — maximum latitude.",
    required=False,
),
ParamDefinition(
    name="min_lon",
    type=ParamType.NUMBER,
    description="Region bounding box — minimum longitude.",
    required=False,
),
ParamDefinition(
    name="max_lon",
    type=ParamType.NUMBER,
    description="Region bounding box — maximum longitude.",
    required=False,
),
```

Add to SELECT: `airline, airline_code` (useful for CountByField demos).

### Pattern 4: Polygon Map Widget (Frontend)
**What:** New React component `PolygonMapWidget` that renders as a full-screen or modal overlay with a Leaflet map. User clicks to add vertices; component stores them and emits on confirm.
**Pattern:** `useMapEvents` from react-leaflet captures clicks; local state holds vertex list; `Polyline` renders the shape in progress.
**Example:**
```typescript
// PolygonMapWidget.tsx — simplified pattern
import { MapContainer, TileLayer, Polyline, useMapEvents } from 'react-leaflet';

function ClickCapture({ onAdd }: { onAdd: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      onAdd(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// Polygon stored as [[lat, lon], [lat, lon], ...]
// On "Confirm": call updateParam with the array
// On "Clear": reset vertices
// On "Close/Cancel": close without saving
```

**widget_hint branch in ParamField.tsx:**
```typescript
if (param.widget_hint === 'polygon') {
  return (
    <PolygonField
      value={currentValue as number[][] | undefined}
      onChange={updateParam}
    />
  );
}
```

`PolygonField` renders a button showing vertex count (or "Draw geofence") that opens the `PolygonMapWidget` overlay.

### Pattern 5: Backend Dockerfile (multi-stage with uv)
**What:** Two-stage build: uv-based installer stage, then slim Python runtime.
**Key details:**
- uv.lock is in `backend/` — must be in Docker build context
- DATABASE_URL comes from environment (not baked in)
- Config currently reads `env_file: "../.env"` — in Docker, pass DATABASE_URL as environment variable directly; pydantic-settings reads env vars first before file
```dockerfile
# Stage 1: install deps
FROM ghcr.io/astral-sh/uv:0.9.26 AS uv
FROM python:3.12-slim AS builder

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: runtime
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/

ENV PATH="/app/.venv/bin:$PATH"
ENV DATABASE_URL=""

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Pattern 6: Frontend Dockerfile (multi-stage pnpm + nginx)
**What:** Two-stage: node build, then nginx runtime.
**Key details:**
- pnpm 10.x — use `corepack enable && corepack prepare pnpm@10.28.2 --activate` in build stage
- vite builds to `frontend/dist/`
- nginx needs try_files for SPA fallback
- nginx proxies `/api` to backend service name (e.g., `http://backend:8000`)
```dockerfile
# Stage 1: build
FROM node:24-alpine AS builder
RUN corepack enable

WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# Stage 2: nginx
FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Pattern 7: nginx.conf for SPA + /api proxy
```nginx
server {
    listen 80;

    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend service
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # SSE: disable buffering for streaming endpoints
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding on;
    }

    location /health {
        proxy_pass http://backend:8000/health;
    }
}
```

### Pattern 8: docker-compose.yml
```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: ${DATABASE_URL}
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
```

### Anti-Patterns to Avoid
- **Don't query `country` or `region` columns in flight_metadata** — they do not exist; use lat/lon bounding box for region filtering
- **Don't add full_report JSONB to GetAnomalies default outputs** — it is large and will hit row limit fast; exclude by default or make it opt-in
- **Don't use PostGIS** — Tracer 42 RDS does not have PostGIS extension; polygon filtering must remain Python-side ray-casting (already established in Phase 2)
- **Don't use a third-party Leaflet drawing plugin** (leaflet-draw) — react-leaflet 5.x useMapEvents is sufficient and avoids compatibility issues
- **Don't call `ANY(:ids)` with an empty list** — PostgreSQL errors on empty array in ANY(); always guard with `if not flight_ids: return early`
- **Don't bake DATABASE_URL into Docker image** — pass via environment variable at runtime
- **Don't use nginx `proxy_pass http://backend:8000/` with trailing slash for /api/** — be consistent with path rewriting to avoid double-slash issues

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Groupby aggregation | Custom Python loop with dict counting | pandas DataFrame.groupby().size() | Handles None/NaN, sorting, type coercion |
| Polygon click capture on map | Custom event listeners on map div | react-leaflet useMapEvents | Already in package, integrates with React lifecycle |
| Polygon rendering in progress | SVG overlay | react-leaflet Polyline + CircleMarker | Integrated with Leaflet coordinate system |
| nginx SPA routing | Custom 404 handler | try_files $uri /index.html | Standard nginx SPA pattern |
| SSE proxying | Custom streaming handler | nginx proxy_buffering off + chunked | Required for SSE to work through nginx |
| Docker layer caching for uv | Copy all source first | Copy pyproject.toml + uv.lock first, then sync | Dependency layer cached unless lock changes |

## Common Pitfalls

### Pitfall 1: Empty flight_ids array crashes ANY() in PostgreSQL
**What goes wrong:** `WHERE flight_id = ANY(:ids)` with `ids=[]` raises `asyncpg.exceptions.DataError` — PostgreSQL cannot infer type of empty array.
**Why it happens:** asyncpg needs a typed array; empty Python list has no type hint.
**How to avoid:** Guard at the top of `execute()`: `if not flight_ids: return {"anomalies": [], "flight_ids": []}`. If you must pass empty, cast: `text("= ANY(ARRAY[]::text[])")`.
**Warning signs:** `DataError: could not determine data type` in logs.

### Pitfall 2: Config reads ../. env — breaks inside Docker
**What goes wrong:** `backend/app/config.py` has `env_file: "../.env"` (relative path). Inside Docker, this path does not exist.
**Why it happens:** Path is relative to where uvicorn is launched, not the project root.
**How to avoid:** pydantic-settings reads environment variables before file — if `DATABASE_URL` is set as an env var in docker-compose, it takes precedence and the missing .env file is silently ignored. No code change needed.
**Warning signs:** `DATABASE_URL` defaulting to `postgresql+asyncpg://localhost:5432/tracer` inside container.

### Pitfall 3: nginx SSE buffering breaks the SSE stream
**What goes wrong:** nginx buffers proxy responses by default; SSE events do not reach the browser until nginx buffer fills or times out.
**Why it happens:** `proxy_buffering on` is the default.
**How to avoid:** Add `proxy_buffering off; proxy_cache off;` to the `/api/` location block. Also set `proxy_http_version 1.1` and `chunked_transfer_encoding on`.
**Warning signs:** SSE cube status updates don't appear during execution, all arrive at once at the end.

### Pitfall 4: pnpm-lock.yaml vs pnpm-lock.yaml name in Docker
**What goes wrong:** `pnpm install --frozen-lockfile` fails if the lock file is missing in the Docker build context.
**Why it happens:** The lock file is called `pnpm-lock.yaml` (check exact name in frontend/).
**How to avoid:** `COPY package.json pnpm-lock.yaml ./` in Dockerfile — verify exact filename first.
**Warning signs:** `ENOENT: no such file or directory pnpm-lock.yaml` during build.

### Pitfall 5: polygon widget_hint on a JSON_OBJECT param conflicts with textarea fallback
**What goes wrong:** If `widget_hint === 'polygon'` check is not placed before the `switch (param.type)` block, the JSON_OBJECT textarea renders instead.
**Why it happens:** Current ParamField.tsx checks widget_hint only for `relative_time` and `datetime` — JSON_OBJECT falls through to textarea.
**How to avoid:** Add `polygon` widget_hint check in the `if (param.widget_hint === ...)` chain at the top of `renderInput()`, before the switch.

### Pitfall 6: CountByField receives connected upstream full result (JSON_OBJECT with nested data)
**What goes wrong:** When wiring `AllFlights.__full_result__` to CountByField's `data` param, the value is `{"flights": [...], "flight_ids": [...]}` not the array directly.
**Why it happens:** Full Result bundles all outputs into a single dict.
**How to avoid:** CountByField should accept either a plain array OR a dict with a `flights`/`anomalies` key. Add logic: `if isinstance(data, dict): data = next((v for v in data.values() if isinstance(v, list)), [])`. This handles full_result connection gracefully.

### Pitfall 7: uv.lock not copied in Dockerfile
**What goes wrong:** `uv sync --frozen` fails if uv.lock is not in the Docker build context.
**Why it happens:** uv requires the lock file to install exact versions.
**How to avoid:** Build context must be `./backend` and the Dockerfile must `COPY uv.lock ./`.
**Warning signs:** `uv sync --frozen` exits with "No lockfile found".

## Code Examples

### GetAnomalies — complete execute() pattern
```python
# Source: mirrors AllFlights pattern (established Phase 02)
async def execute(self, **inputs: Any) -> dict[str, Any]:
    flight_ids = inputs.get("flight_ids") or []
    min_severity = inputs.get("min_severity")

    if not flight_ids:
        return {"anomalies": [], "flight_ids": []}

    sql_parts = [
        """
        SELECT id, flight_id, timestamp, is_anomaly,
               severity_cnn, severity_dense,
               callsign, airline, origin_airport, destination_airport,
               aircraft_type, geographic_region, is_military,
               matched_rule_ids, matched_rule_names
        FROM research.anomaly_reports
        WHERE flight_id = ANY(:flight_ids)
        """
    ]
    params: dict[str, Any] = {"flight_ids": list(flight_ids)}

    if min_severity is not None:
        sql_parts.append("AND severity_cnn >= :min_severity")
        params["min_severity"] = float(min_severity)

    full_sql = "\n".join(sql_parts)

    async with engine.connect() as conn:
        result = await conn.execute(text(full_sql), params)
        columns = list(result.keys())
        rows = [dict(zip(columns, row)) for row in result.fetchall()]

    unique_ids = list({r["flight_id"] for r in rows})
    return {"anomalies": rows, "flight_ids": unique_ids}
```

### AllFlights — airport filter addition
```python
# Add after callsign filter block in execute()
airport = inputs.get("airport")
if airport:
    sql_parts.append(
        "AND (origin_airport ILIKE :airport OR destination_airport ILIKE :airport)"
    )
    params["airport"] = f"%{airport}%"

# Add bounding box filter
min_lat = inputs.get("min_lat")
max_lat = inputs.get("max_lat")
min_lon = inputs.get("min_lon")
max_lon = inputs.get("max_lon")
if all(v is not None for v in [min_lat, max_lat, min_lon, max_lon]):
    sql_parts.append(
        "AND start_lat BETWEEN :min_lat AND :max_lat "
        "AND start_lon BETWEEN :min_lon AND :max_lon"
    )
    params.update({"min_lat": float(min_lat), "max_lat": float(max_lat),
                   "min_lon": float(min_lon), "max_lon": float(max_lon)})
```

### AllFlights — add airline to SELECT columns
```python
# Update the SELECT to include airline + airline_code
sql_parts = [
    """
    SELECT
        flight_id, callsign, airline, airline_code,
        first_seen_ts, last_seen_ts,
        min_altitude_ft, max_altitude_ft,
        origin_airport, destination_airport,
        is_anomaly, is_military,
        start_lat, start_lon, end_lat, end_lon
    FROM research.flight_metadata
    WHERE 1=1
    """
]
```

### CountByField — handling full_result dict input
```python
async def execute(self, **inputs: Any) -> dict[str, Any]:
    data = inputs.get("data") or []
    group_by_field = inputs.get("group_by_field", "")

    # Handle full_result connection: {"flights": [...], "flight_ids": [...]}
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])

    if not data or not group_by_field:
        return {"counts": []}

    df = pd.DataFrame(data)
    if group_by_field not in df.columns:
        return {"counts": []}

    grouped = (
        df.groupby(group_by_field, dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    return {
        "counts": [
            {"value": str(row[group_by_field]), "count": int(row["count"])}
            for _, row in grouped.iterrows()
        ]
    }
```

### PolygonMapWidget — overlay component structure
```typescript
// frontend/src/components/CubeNode/PolygonMapWidget.tsx
import { useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, useMapEvents } from 'react-leaflet';

interface Props {
  initialPolygon?: number[][];
  onConfirm: (polygon: number[][]) => void;
  onClose: () => void;
}

function ClickCapture({ onAdd }: { onAdd: (lat: number, lng: number) => void }) {
  useMapEvents({ click(e) { onAdd(e.latlng.lat, e.latlng.lng); } });
  return null;
}

export function PolygonMapWidget({ initialPolygon, onConfirm, onClose }: Props) {
  const [points, setPoints] = useState<number[][]>(initialPolygon ?? []);

  const addPoint = (lat: number, lng: number) =>
    setPoints((prev) => [...prev, [lat, lng]]);

  const leafletPoints = points.map(([lat, lon]) => [lat, lon] as [number, number]);

  return (
    <div className="polygon-widget-overlay nodrag nowheel" onClick={(e) => e.stopPropagation()}>
      <MapContainer center={[32, 35]} zoom={6} style={{ height: '400px', width: '100%' }}>
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        <ClickCapture onAdd={addPoint} />
        {leafletPoints.length > 1 && <Polyline positions={leafletPoints} />}
        {leafletPoints.map(([lat, lon], i) => (
          <CircleMarker key={i} center={[lat, lon]} radius={5} />
        ))}
      </MapContainer>
      <div className="polygon-widget-controls">
        <button onClick={() => setPoints([])}>Clear</button>
        <button onClick={onClose}>Cancel</button>
        <button onClick={() => { onConfirm(points); onClose(); }} disabled={points.length < 3}>
          Confirm ({points.length} pts)
        </button>
      </div>
    </div>
  );
}
```

### PolygonField button in ParamField
```typescript
// Inside renderInput() in ParamField.tsx, before the switch:
if (param.widget_hint === 'polygon') {
  const polygon = currentValue as number[][] | undefined;
  return (
    <PolygonField
      value={polygon}
      onChange={updateParam}
      paramDescription={param.description}
    />
  );
}
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| leaflet-draw plugin for polygon drawing | react-leaflet useMapEvents (click events) | Fewer deps, no React 18 compat issues |
| pip/poetry for Docker deps | uv sync --frozen in multi-stage | Faster builds, deterministic via lock file |
| nginx full config file | nginx/conf.d/default.conf snippet | Simpler — overrides default.conf only |

**Confirmed schema facts:**
- `flight_metadata` does NOT have `country` or `region` columns — lat/lon bounding box is the only way to do region filtering at the SQL level
- `flight_metadata` DOES have `airline`, `airline_code` — perfect group-by fields for Count By Field demos
- `anomaly_reports` has `geographic_region` (text), `severity_cnn` (float), `severity_dense` (float), `full_report` (JSONB — skip by default, too large)
- Both tables are in `research` schema (confirmed working via live queries)

## Open Questions

1. **pnpm-lock.yaml exact filename**
   - What we know: pnpm generates either `pnpm-lock.yaml` or `pnpm-lockfile.yaml` depending on version
   - What's unclear: Exact filename in this project (not checked directly)
   - Recommendation: Planner should specify `COPY package.json pnpm-lock.yaml ./` and verify before executing

2. **Polygon widget z-index / positioning on CubeNode**
   - What we know: CubeNode is inside React Flow canvas with `position: absolute`
   - What's unclear: Whether a full-screen overlay from inside a CubeNode needs a portal to escape the canvas stacking context
   - Recommendation: Use `position: fixed` with high z-index (9999) for the overlay div, or render via React portal to `document.body`. The `nodrag nowheel` class prevents canvas interference.

3. **Docker CORS — frontend at port 3000, backend at 8000**
   - What we know: `config.py` has `cors_origins: ["http://localhost:3000", "http://localhost:5173"]`
   - What's unclear: In production Docker, browser hits port 3000 (nginx), nginx proxies to backend:8000. CORS origin will be `http://localhost:3000` which is already in the allowed list.
   - Recommendation: No code change needed for CORS in Docker setup.

## Sources

### Primary (HIGH confidence)
- Live DB schema queries — `research.flight_metadata` and `research.anomaly_reports` columns confirmed directly via asyncpg connection to Tracer 42 RDS
- `backend/app/cubes/all_flights.py` — existing AllFlights pattern for engine.connect(), SQL construction, polygon filtering
- `backend/app/cubes/base.py` — BaseCube contract: execute(**inputs) → dict[str, Any]
- `backend/app/engine/executor.py` — stream_graph, row limit application, full_result bundling
- `frontend/src/components/CubeNode/ParamField.tsx` — widget_hint branch pattern (relative_time, datetime)
- `frontend/package.json` — confirmed react-leaflet 5.0.0, leaflet 1.9.4 already installed
- `backend/pyproject.toml` — confirmed pandas NOT in dependencies
- `backend/uv.lock` — confirmed uv.lock exists at backend/

### Secondary (MEDIUM confidence)
- react-leaflet 5.x docs pattern for useMapEvents — standard hook, no breaking changes between 4.x and 5.x for this use case
- uv Docker documentation pattern — ghcr.io/astral-sh/uv official image, multi-stage build with `uv sync --frozen`
- nginx SPA configuration — try_files $uri /index.html is the universally documented pattern
- nginx SSE proxy — proxy_buffering off is the documented requirement for SSE

### Tertiary (LOW confidence — flag for validation)
- pnpm lock file exact filename — assumed `pnpm-lock.yaml` but not directly verified

## Metadata

**Confidence breakdown:**
- DB schema (AllFlights enhancement, GetAnomalies columns): HIGH — queried live DB
- CountByField pandas pattern: HIGH — standard pandas API
- Docker patterns (uv multi-stage, nginx SPA): HIGH — well-established, cross-verified
- Polygon widget (useMapEvents): HIGH — react-leaflet 5 already installed, same API
- Country/region column absence: HIGH — confirmed via live DB query

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (DB schema stable; library versions stable)
