# Phase 2: Backend Core — Registry, DB, CRUD, Executor - Research

**Researched:** 2026-03-03
**Domain:** FastAPI + SQLAlchemy async + Alembic + topological sort + polygon point-in-polygon
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Execution response shape:**
- Per-cube results as array-of-objects (row-based table format)
- Each row is an object with the same keys, different values
- Response keyed by node_id with status + outputs per cube
- Example structure:
  ```json
  {
    "node-1": {
      "status": "done",
      "outputs": {
        "flights": [
          {"flight_id": "ABC123", "callsign": "ELY001", "altitude": 35000},
          {"flight_id": "DEF456", "callsign": "THY502", "altitude": 28000}
        ]
      },
      "truncated": false
    }
  }
  ```

**Failure behavior:**
- Independent branches continue executing when a cube fails
- Failed cube gets `"status": "error"` with error message
- Downstream dependents of the failed cube are skipped (marked as skipped with reason)
- All other cubes with satisfied dependencies still execute

**Cubes to build:**
- **echo_cube** — Test stub that echoes its input
- **add_numbers** — Test stub that adds two numbers
- **all_flights** — Real production cube querying `research.flight_metadata` (and joining `research.normal_tracks` for polygon/position-based filtering)

**All Flights cube parameters:**
- **Time filter:** Accepts relative time (last X hours/minutes/seconds) OR absolute time range (two datetimes)
- **Flight IDs:** Input param accepting list_of_strings — manual entry or from connection
- **Callsign:** String filter
- **Altitude range:** Min/max altitude range — filters flights where all points are between the specified altitudes
- **Polygon geofence:** Array of lat/lon coordinate pairs defining a boundary — filters flights that had positions within the polygon (queries `research.normal_tracks` for position data)

**Data sources:**
- `research.flight_metadata` — Primary table for flight metadata queries (time, callsign, flight IDs)
- `research.normal_tracks` — Flight track/position data, used for polygon geofence filtering and altitude filtering along the flight path

### Claude's Discretion
- CubeRegistry auto-discovery mechanism (importlib vs pkgutil vs __init__ registration)
- Alembic migration structure and naming
- Exact SQL query construction for the flights cube
- How polygon point-in-polygon check is implemented (PostGIS vs manual calculation)
- WorkflowExecutor internal architecture (dependency graph representation)
- Error message formatting
- How "skipped" status is communicated for dependents of failed cubes

### Deferred Ideas (OUT OF SCOPE)
- Polygon drawing/dragging UI on the canvas — frontend phase (Phase 4 or 6)
- Additional real data cubes (filter_flights, get_anomalies, count_by_field) — Phase 7
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-03 | CubeRegistry that auto-discovers all BaseCube subclasses from the cubes package and exposes them by cube_id | pkgutil.iter_modules pattern verified; BaseCube.definition property already exists |
| BACK-04 | SQLAlchemy Workflow model (UUID pk, name, graph_json JSONB, created_at, updated_at) in public schema | SQLAlchemy 2.0 mapped_column + JSONB type confirmed; Base class exists in database.py |
| BACK-05 | Alembic migration creating public.workflows table | Alembic async template verified; env.py pattern from installed version confirmed |
| BACK-06 | GET /api/cubes/catalog returns all registered cube definitions as JSON array | Simple router using registry singleton; CubeDefinition Pydantic model already defined |
| BACK-07 | Workflow CRUD API — POST/GET/PUT/DELETE /api/workflows[/{id}] | Async CRUD pattern with SQLAlchemy select/insert/update/delete confirmed; WorkflowResponse schema exists |
| BACK-08 | POST /api/workflows/{id}/run executes workflow and returns results | Executor takes WorkflowGraph from DB, returns dict keyed by node_id |
| BACK-09 | WorkflowExecutor: topological sort, cycle detection (400), input resolution from connections, type validation | Kahn's algorithm for topo sort + cycle detection; connection resolution logic defined |
| BACK-10 | Full Result port (__full_result__) bundles all cube outputs into one JSON object | BaseCube already appends __full_result__ output; executor bundles outputs dict |
| BACK-11 | Result rows capped at 100 per cube with truncation flag | settings.result_row_limit=100 already in config; slicing + truncated flag pattern |
| BACK-12 | Connection values override manually entered param values at execution time | Input resolution: merge manual params + connection-provided values (connections win) |
</phase_requirements>

---

## Summary

Phase 2 constructs the full backend runtime from existing scaffolding (schemas, BaseCube, config, database). All critical Pydantic schemas and the database connection layer are already complete. This phase adds four new components: CubeRegistry (auto-discovery), SQLAlchemy Workflow ORM model, Alembic migration, workflow CRUD router, WorkflowExecutor (topo sort + execution), and three cubes (two stubs + one real DB cube).

The critical discovery from live database inspection: **PostGIS is NOT installed** on the Tracer 42 RDS instance. Polygon geofence filtering must use pure Python ray-casting (point-in-polygon algorithm), querying `research.normal_tracks` for lat/lon points and filtering in Python. The `normal_tracks` schema is confirmed: flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source.

The `research.flight_metadata` table uses **bigint epoch timestamps** (not datetime) for `first_seen_ts` and `last_seen_ts`, and pre-aggregates altitude ranges as `min_altitude_ft`/`max_altitude_ft` columns — altitude filtering can be done directly in SQL without joining normal_tracks. The polygon filter is the only reason to join `normal_tracks`.

**Primary recommendation:** Use pkgutil-based auto-discovery for the registry, Kahn's algorithm for topological sort, pure Python ray-casting for polygon geofence, and a clean dependency graph dict for the executor internal state.

---

## Standard Stack

### Core (already installed in pyproject.toml)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | HTTP framework + dependency injection | Already in use (main.py) |
| SQLAlchemy | >=2.0.0 | ORM + async session | Already in use (database.py) |
| asyncpg | >=0.30.0 | Async PostgreSQL DBAPI | Already in use (database.py) |
| alembic | >=1.14.0 | Database migrations | Already installed |
| pydantic | >=2.0.0 | Data contracts | Already in use (all schemas) |

### No New Dependencies Needed

All required libraries are already installed. This phase requires zero new package additions.

**Verification:** `pkgutil`, `importlib`, `collections` (for deque in Kahn's), and `typing` are all Python stdlib. Polygon point-in-polygon is pure Python math.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── engine/
│   ├── __init__.py          # empty (exists)
│   ├── registry.py          # NEW: CubeRegistry singleton
│   └── executor.py          # NEW: WorkflowExecutor
├── models/
│   ├── __init__.py          # empty (exists)
│   └── workflow.py          # NEW: SQLAlchemy Workflow ORM model
├── routers/
│   ├── __init__.py          # empty (exists)
│   ├── cubes.py             # NEW: GET /api/cubes/catalog
│   └── workflows.py         # NEW: CRUD + run endpoints
├── cubes/
│   ├── __init__.py          # empty (exists, keep empty — registry scans)
│   ├── base.py              # exists: BaseCube abstract class
│   ├── echo_cube.py         # NEW: EchoCube stub
│   ├── add_numbers.py       # NEW: AddNumbers stub
│   └── all_flights.py       # NEW: AllFlights real DB cube
backend/alembic/
│   ├── env.py               # NEW: async Alembic env
│   └── versions/
│       └── 001_create_workflows.py  # NEW: first migration
backend/alembic.ini          # NEW: Alembic config pointing to alembic/ dir
```

### Pattern 1: CubeRegistry with pkgutil Auto-Discovery

**What:** Scan the `cubes` package at startup using `pkgutil.iter_modules`, import each module, find BaseCube subclasses using `__subclasses__()`, build a dict keyed by `cube_id`.

**When to use:** Any time new cubes are added — zero registration boilerplate.

**Why pkgutil over alternatives:**
- `importlib` approach requires knowing module names in advance
- `__init__.py` registration approach requires manual updates
- `pkgutil.iter_modules` is the standard "scan a package" pattern — stdlib, no overhead

**Example:**
```python
# Source: Python stdlib pkgutil + importlib pattern
import importlib
import pkgutil
from app.cubes.base import BaseCube
import app.cubes as cubes_pkg

class CubeRegistry:
    def __init__(self):
        self._cubes: dict[str, BaseCube] = {}

    def load(self) -> None:
        """Import all modules in the cubes package, triggering subclass registration."""
        for module_info in pkgutil.iter_modules(cubes_pkg.__path__):
            if module_info.name == "base":
                continue
            importlib.import_module(f"app.cubes.{module_info.name}")
        # After imports, walk subclasses
        for cls in BaseCube.__subclasses__():
            instance = cls()
            self._cubes[instance.cube_id] = instance

    def get(self, cube_id: str) -> BaseCube | None:
        return self._cubes.get(cube_id)

    def all(self) -> list[BaseCube]:
        return list(self._cubes.values())

# Singleton created at module level
registry = CubeRegistry()
registry.load()
```

**Key insight:** `BaseCube.__subclasses__()` only returns classes that have been imported. The pkgutil scan triggers the imports, which registers the subclasses.

### Pattern 2: SQLAlchemy 2.0 Workflow Model with JSONB

**What:** Declarative mapped_column style (SQLAlchemy 2.0), JSONB column for graph storage, UUID primary key, server-side timestamps.

**Example:**
```python
# Source: SQLAlchemy 2.0 mapped_column API
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, default="Untitled Workflow")
    graph_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

**Important:** JSONB is in `sqlalchemy.dialects.postgresql`. Using `JSON` (generic) would work but JSONB is more efficient for PostgreSQL.

### Pattern 3: Alembic with Async SQLAlchemy

**What:** Alembic needs special handling for async SQLAlchemy — use the `async` template, override URL from app settings (not alembic.ini), import model metadata for autogenerate.

**Example env.py:**
```python
# Source: Alembic async template (verified from installed package)
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.database import Base
from app.models import workflow  # noqa: import triggers model registration

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override URL from app settings (not alembic.ini)
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.async_database_url)

target_metadata = Base.metadata

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Critical pitfall:** The env.py MUST import the model modules before `target_metadata = Base.metadata` — otherwise the tables won't be registered and autogenerate won't see them.

**Manual migration (safer):** Write the migration manually instead of using autogenerate, since the schema is simple and known in advance.

### Pattern 4: WorkflowExecutor — Kahn's Algorithm Topological Sort

**What:** Build adjacency list from edges, compute in-degree per node, use queue-based Kahn's algorithm. Cycle detection: if processed nodes < total nodes, a cycle exists.

**Example:**
```python
# Source: Kahn's algorithm — standard CS algorithm
from collections import deque, defaultdict

def topological_sort(nodes: list[WorkflowNode], edges: list[WorkflowEdge]) -> list[str]:
    """Return ordered list of node IDs. Raises ValueError on cycle."""
    node_ids = {n.id for n in nodes}
    in_degree = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        adjacency[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue = deque(nid for nid in node_ids if in_degree[nid] == 0)
    order = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for successor in adjacency[nid]:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    if len(order) != len(node_ids):
        raise ValueError("Workflow graph contains a cycle")

    return order
```

### Pattern 5: Input Resolution — Connections Override Manual Values

**What:** For each node being executed, start with the node's manually-entered `data.params` dict, then overlay values from incoming edges (connection values override manual values).

**Example:**
```python
def resolve_inputs(
    node: WorkflowNode,
    edges: list[WorkflowEdge],
    results: dict[str, dict],  # {node_id: {"outputs": {...}}}
) -> dict[str, Any]:
    """Merge manual params with connection-provided values. Connections win."""
    inputs = dict(node.data.params)  # start with manual values

    for edge in edges:
        if edge.target != node.id:
            continue
        source_outputs = results.get(edge.source, {}).get("outputs", {})
        if edge.sourceHandle == "__full_result__":
            # Full Result bundles all outputs into one JSON object
            value = source_outputs
        else:
            value = source_outputs.get(edge.sourceHandle)

        if edge.targetHandle and value is not None:
            inputs[edge.targetHandle] = value

    return inputs
```

### Pattern 6: Executor Failure Isolation

**What:** Track which nodes have failed. Before executing a node, check if any of its source nodes are in the failed or skipped set. If so, mark it as skipped.

**Example:**
```python
async def execute_graph(graph: WorkflowGraph, registry: CubeRegistry) -> dict:
    try:
        order = topological_sort(graph.nodes, graph.edges)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    node_map = {n.id: n for n in graph.nodes}
    results: dict[str, Any] = {}
    failed_or_skipped: set[str] = set()

    for node_id in order:
        node = node_map[node_id]
        # Check if any dependency failed/skipped
        source_ids = {e.source for e in graph.edges if e.target == node_id}
        if source_ids & failed_or_skipped:
            results[node_id] = {
                "status": "skipped",
                "reason": "upstream cube failed or was skipped",
                "outputs": {},
            }
            failed_or_skipped.add(node_id)
            continue

        cube = registry.get(node.data.cube_id)
        if cube is None:
            results[node_id] = {"status": "error", "message": f"Unknown cube: {node.data.cube_id}", "outputs": {}}
            failed_or_skipped.add(node_id)
            continue

        inputs = resolve_inputs(node, graph.edges, results)
        try:
            outputs = await cube.execute(**inputs)
            # Apply row limit + truncated flag per list output
            capped_outputs, truncated = apply_row_limit(outputs, limit=100)
            results[node_id] = {"status": "done", "outputs": capped_outputs, "truncated": truncated}
        except Exception as e:
            results[node_id] = {"status": "error", "message": str(e), "outputs": {}}
            failed_or_skipped.add(node_id)

    return results
```

### Pattern 7: AllFlights Cube — SQL Query Construction

**What:** Build a parameterized SQL query against `research.flight_metadata`. Apply time filter, callsign filter, altitude filter, and flight_ids filter directly in SQL. Polygon filter requires a JOIN to `research.normal_tracks` with Python ray-casting.

**Confirmed schema from live DB:**
- Time: `first_seen_ts` and `last_seen_ts` are **bigint Unix epoch seconds**
- Altitude: `min_altitude_ft` and `max_altitude_ft` pre-computed in flight_metadata
- Callsign: `callsign` column (text)
- Flight IDs: `flight_id` column (text)
- Normal tracks: `lat`, `lon`, `alt`, `flight_id`, `timestamp` columns

**Time filter implementation:**
```python
import time

# Relative time: last X seconds
cutoff_ts = int(time.time()) - last_seconds
WHERE first_seen_ts >= cutoff_ts OR last_seen_ts >= cutoff_ts

# Absolute time range (epoch seconds from frontend)
WHERE first_seen_ts <= end_epoch AND last_seen_ts >= start_epoch
```

**Altitude filter (direct SQL — no join needed):**
```python
# "all points between altitudes" — use pre-aggregated min/max columns
WHERE min_altitude_ft >= min_alt AND max_altitude_ft <= max_alt
```

**Polygon filter (Python ray-casting — PostGIS NOT available):**
```python
# 1. Get candidate flight_ids from flight_metadata matching other filters
# 2. Fetch their track points from normal_tracks
# 3. Apply ray-casting point-in-polygon per point
# 4. Keep flights that had ANY point inside the polygon

def point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(polygon)
    inside = False
    x, y = lon, lat
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][1], polygon[i][0]  # lon, lat
        xj, yj = polygon[j][1], polygon[j][0]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
```

**Query strategy for polygon (two-phase):**
```python
# Phase 1: SQL with all non-polygon filters → candidate flight_ids
# Phase 2: fetch tracks for candidates, filter by polygon in Python
# This avoids loading ALL tracks; only loads tracks for filtered candidates
```

### Anti-Patterns to Avoid

- **Registering cubes in `cubes/__init__.py`:** Breaks auto-discovery and requires manual updates. Keep `__init__.py` empty.
- **Using `asyncio.run()` inside FastAPI route handlers:** Routes are already in an async context. Using `asyncio.run()` creates nested event loops. Use `await` directly.
- **`alembic init` without `--template async`:** The generic template uses sync SQLAlchemy. With asyncpg, must use the async template pattern.
- **Ignoring `expire_on_commit=False`:** Already set in `database.py`. Without it, accessing ORM attributes after `session.commit()` triggers lazy loads that fail in async context.
- **Polygon as nested JSON vs flat list:** Frontend will send polygon as list of `[lat, lon]` pairs. Accept as `list[list[float]]` in Pydantic, not a custom object.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Topological sort | Custom DFS sort | Kahn's algorithm (stdlib only) | Kahn's naturally detects cycles via remaining in-degree counts |
| Point-in-polygon | PostGIS ST_Contains | Pure Python ray-casting | PostGIS not installed on Tracer 42 RDS |
| UUID generation | Custom IDs | `uuid.uuid4()` as SQLAlchemy default | Standard, no collisions |
| JSONB serialization | Custom JSON handling | SQLAlchemy JSONB type | Handles serialization/deserialization automatically |
| Async session management | Manual connection pooling | `async_sessionmaker` (already in database.py) | Handles pool, cleanup, exception rollback |
| Migration state | Manual SQL scripts | Alembic versioned migrations | Tracks applied migrations, supports rollback |

**Key insight:** The polygon filter is the only custom algorithm needed, and it's 15 lines of standard ray-casting that every CS textbook covers.

---

## Common Pitfalls

### Pitfall 1: Alembic Can't Find Models for Autogenerate

**What goes wrong:** Running `alembic revision --autogenerate` produces an empty migration with no table creation.

**Why it happens:** `env.py` sets `target_metadata = Base.metadata` but never imports the model modules. SQLAlchemy's declarative system only registers a model when its class is imported.

**How to avoid:** In `env.py`, explicitly import all model modules before using `Base.metadata`:
```python
from app.models import workflow  # noqa: triggers Workflow class registration
```

**Warning signs:** Migration file says `def upgrade() -> None: pass`.

### Pitfall 2: JSONB vs JSON Column — Serialization of WorkflowGraph

**What goes wrong:** Storing a `WorkflowGraph` Pydantic model in a JSONB column requires serialization to dict first.

**Why it happens:** SQLAlchemy JSONB accepts native Python dicts. Pydantic models are not dicts.

**How to avoid:** When saving, call `graph.model_dump()`. When loading, reconstruct with `WorkflowGraph.model_validate(row.graph_json)`.

```python
# Saving
workflow.graph_json = graph_data.graph_json.model_dump()
# Loading
graph = WorkflowGraph.model_validate(workflow.graph_json)
```

### Pitfall 3: UUID Primary Keys in SQLAlchemy Async — `returning()` Needed

**What goes wrong:** After `session.add(workflow)` and `session.commit()`, accessing `workflow.id` raises `MissingGreenlet` or returns None.

**Why it happens:** With `expire_on_commit=False` set (as in database.py), the object is not expired but the UUID default is generated client-side (`default=uuid.uuid4`), so it IS available. No special handling needed IF `default` is set on the column (not `server_default`).

**How to avoid:** Use `default=uuid.uuid4` (Python-side default), not `server_default=gen_random_uuid()`. With Python-side default, the UUID is assigned before the INSERT.

### Pitfall 4: BigInt Epoch Timestamps in flight_metadata

**What goes wrong:** Treating `first_seen_ts` / `last_seen_ts` as milliseconds instead of seconds, resulting in time filters that never match (comparing epoch seconds against epoch milliseconds is 1000x off).

**Why it happens:** Some systems use milliseconds, some use seconds. Tracer 42 uses seconds (confirmed from live schema).

**How to avoid:** Use `int(time.time())` for current time (seconds). Document the unit clearly in the cube.

### Pitfall 5: WorkflowExecutor — Running in Router Without DB Session Awareness

**What goes wrong:** The executor receives a `WorkflowGraph` object but cubes that query the DB need a database connection. Passing the FastAPI session to the executor couples the executor to FastAPI.

**Why it happens:** Design ambiguity between router-level dependencies and cube-level resource needs.

**How to avoid:** Cubes that need DB access use `get_raw_connection()` or create their own connections via the engine directly. The executor does NOT pass a session to cubes — cubes acquire their own connections. This keeps BaseCube.execute() signature clean (`**inputs` only).

### Pitfall 6: `__subclasses__()` Only Returns Direct Subclasses

**What goes wrong:** If cubes inherit from an intermediate class (e.g., `class FlightCube(BaseCube)`), `BaseCube.__subclasses__()` returns `FlightCube` but not `AllFlights(FlightCube)`.

**Why it happens:** `__subclasses__()` is not recursive.

**How to avoid:** All cubes must directly subclass `BaseCube`. No intermediate classes in this phase. Alternatively, use a recursive `__subclasses__` walk — but given current design, direct subclassing is simpler.

### Pitfall 7: Polygon Input Type — Accepting Variable Formats

**What goes wrong:** Frontend sends polygon as `[[lat, lon], [lat, lon], ...]`. Backend tries to parse it as a Pydantic model and fails.

**Why it happens:** JSON arrays of arrays don't map cleanly to named Pydantic fields.

**How to avoid:** Accept polygon as `list[list[float]] | None` in the cube's input param (as `json_object` ParamType). Validate inside `execute()` that it has the right shape.

---

## Code Examples

### EchoCube Stub
```python
# backend/app/cubes/echo_cube.py
from typing import Any
from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class EchoCube(BaseCube):
    cube_id = "echo"
    name = "Echo"
    description = "Echoes its input value back as output"
    category = CubeCategory.OUTPUT
    inputs = [
        ParamDefinition(name="value", type=ParamType.STRING, description="Value to echo")
    ]
    outputs = [
        ParamDefinition(name="result", type=ParamType.STRING, description="Echoed value")
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        return {"result": inputs.get("value", "")}
```

### AddNumbers Stub
```python
# backend/app/cubes/add_numbers.py
from typing import Any
from app.cubes.base import BaseCube
from app.schemas.cube import CubeCategory, ParamDefinition, ParamType


class AddNumbersCube(BaseCube):
    cube_id = "add_numbers"
    name = "Add Numbers"
    description = "Adds two numbers together"
    category = CubeCategory.ANALYSIS
    inputs = [
        ParamDefinition(name="a", type=ParamType.NUMBER, description="First number"),
        ParamDefinition(name="b", type=ParamType.NUMBER, description="Second number"),
    ]
    outputs = [
        ParamDefinition(name="sum", type=ParamType.NUMBER, description="Sum of a and b")
    ]

    async def execute(self, **inputs: Any) -> dict[str, Any]:
        a = float(inputs.get("a", 0))
        b = float(inputs.get("b", 0))
        return {"sum": a + b}
```

### Workflow CRUD Router Pattern
```python
# Async CRUD with SQLAlchemy 2.0
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_workflow(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow
```

### Row-Limit Application
```python
def apply_row_limit(outputs: dict[str, Any], limit: int) -> tuple[dict, bool]:
    """Cap list outputs at limit rows. Returns (capped_outputs, any_truncated)."""
    capped = {}
    truncated = False
    for key, value in outputs.items():
        if isinstance(value, list) and len(value) > limit:
            capped[key] = value[:limit]
            truncated = True
        else:
            capped[key] = value
    return capped, truncated
```

### Alembic Manual Migration
```python
# backend/alembic/versions/001_create_workflows.py
"""create workflows table

Revision ID: 001
Revises:
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import uuid

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String, nullable=False, default="Untitled Workflow"),
        sa.Column("graph_json", JSONB, nullable=False, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("workflows")
```

---

## Database Schema (Confirmed from Live DB)

### research.flight_metadata

| Column | Type | Notes |
|--------|------|-------|
| flight_id | text | Primary key-ish (join key) |
| callsign | text | ILIKE filter |
| first_seen_ts | bigint | **Unix epoch seconds** |
| last_seen_ts | bigint | **Unix epoch seconds** |
| min_altitude_ft | double precision | Pre-aggregated — use for altitude filter |
| max_altitude_ft | double precision | Pre-aggregated — use for altitude filter |
| origin_airport | text | |
| destination_airport | text | |
| is_anomaly | boolean | |
| is_military | boolean | |
| start_lat, start_lon | double precision | Origin position |
| end_lat, end_lon | double precision | Destination position |

### research.normal_tracks

| Column | Type | Notes |
|--------|------|-------|
| flight_id | text | Join key to flight_metadata |
| timestamp | bigint | Unix epoch seconds |
| lat | double precision | For polygon filter |
| lon | double precision | For polygon filter |
| alt | double precision | Altitude in ft |
| gspeed | double precision | Ground speed |
| callsign | text | |

**PostGIS status: NOT INSTALLED.** Confirmed via live DB query against pg_extension. All spatial logic must be pure Python.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sync SQLAlchemy | Async SQLAlchemy 2.0 mapped_column | SA 2.0 (2023) | Use `async with session:`, `await session.execute()` |
| `Column()` declarative | `mapped_column()` with type hints | SA 2.0 | Cleaner types, better IDE support |
| Alembic generic template | Alembic async template | Alembic 1.x | Required for asyncpg driver |
| `query.filter()` | `select().where()` | SA 2.0 | Old style deprecated in 2.0 |

**Deprecated/outdated:**
- `session.query(Model).filter(...)`: Use `select(Model).where(...)` with `await session.execute()`
- `Column()` in declarative: Use `mapped_column()` with `Mapped[type]` annotation

---

## Open Questions

1. **Alembic migration for JSONB server_default**
   - What we know: JSONB columns with `server_default` need string SQL expression (`text('{}')` not `{}`)
   - What's unclear: Whether `default=dict` (Python-side) on the ORM model is sufficient for Alembic migration, or if `server_default` is needed
   - Recommendation: Use Python-side `default=dict` on ORM, omit server_default in migration, set default at application level. JSONB column can be `nullable=False` with `default={}` supplied by app code.

2. **AllFlights polygon + other filters interaction**
   - What we know: Polygon filter requires loading tracks from normal_tracks for candidate flights
   - What's unclear: Performance when many flights match non-polygon filters before polygon filtering
   - Recommendation: Apply all SQL-based filters first to reduce candidates, THEN load normal_tracks for the candidate set. Add a LIMIT in the SQL phase (e.g., 5000 candidates max) before polygon check.

3. **WorkflowResponse.id type mismatch**
   - What we know: `WorkflowResponse.id` is `uuid.UUID` in Python; TypeScript expects `string`
   - What's unclear: Whether FastAPI auto-serializes UUID to string in JSON (it does via `json_encoders`)
   - Recommendation: FastAPI + Pydantic v2 serialize UUID as string automatically. No action needed — already confirmed in STATE.md.

---

## Sources

### Primary (HIGH confidence)
- Live database query via asyncpg — confirmed schema of `research.flight_metadata` and `research.normal_tracks`, confirmed PostGIS NOT installed
- Installed source: `/backend/.venv/lib/python3.12/site-packages/alembic/templates/async/env.py` — verified async migration pattern
- Existing code: `backend/app/database.py`, `backend/app/schemas/cube.py`, `backend/app/cubes/base.py` — verified integration points
- Python stdlib: `pkgutil.iter_modules`, `__subclasses__()`, `collections.deque` — stdlib, no version concerns

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 `mapped_column` + `Mapped[]` pattern — confirmed from installed package version (>=2.0.0 in pyproject.toml)
- Kahn's algorithm for topological sort — well-established CS algorithm, cycle detection via remaining in-degree counts is standard

### Tertiary (LOW confidence)
- Performance characteristics of Python ray-casting vs PostGIS for large datasets — not benchmarked on this specific data volume; assumed acceptable since row limit caps output at 100 and polygon check is applied in Python after SQL pre-filtering

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed, verified from pyproject.toml
- Architecture: HIGH — existing code provides clear integration points; patterns are established SQLAlchemy 2.0 / FastAPI conventions
- Database schema: HIGH — directly queried live database
- Pitfalls: HIGH — most are verified from code analysis; polygon/PostGIS pitfall is confirmed from live DB query
- Polygon algorithm: MEDIUM — ray-casting is correct algorithm; performance under load not measured

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable stack — no fast-moving dependencies added this phase)
