# Project 12 — Visual Dataflow Workflow Builder

## Overview

**Project 12** (codename "12") is a subsystem of **Tracer 42**, the parent platform that collects
all flights in Middle East airspace (with plans to expand to more regions) and analyzes them in
real time to detect and alert on anomalies and dangerous events.

Tracer 42 maintains a large PostgreSQL database containing flight metadata, course data, and
anomaly reports. A library of analysis functions already exists for evaluating plane behavior,
course quality, jamming detection, and more.

Project 12's mission is to expose all of that data and logic through a **generic, visual
workflow builder**. Users construct analysis pipelines by dragging "cubes" onto a canvas,
configuring their parameters, and connecting outputs to inputs — no code required. The system
then executes the pipeline against the database and returns structured results.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React (TypeScript) + Vite |
| Canvas / Node Editor | React Flow |
| State Management | Zustand |
| Backend | Python + FastAPI |
| Database | PostgreSQL (existing Tracer 42 DB) |
| ORM | SQLAlchemy |

---

## Core Concepts

### Cubes

A **cube** is a self-contained processing unit on the canvas. Each cube type is defined by a
developer in Python and registered in the backend's cube catalog. A cube has:

- A **name** and **category**
- A list of **input parameters** (left side of the cube)
- A list of **output parameters** (right side of the cube)
- A **Full Result** output port that bundles all outputs into a single object
- An **execute** function that receives inputs and produces outputs

### Cube Categories

| Category | Purpose | Example |
|----------|---------|---------|
| **Data Source** | Query raw data from the database | "All flights in Middle East", "Flights by airport" |
| **Filter** | Narrow down a dataset by criteria | "Flights in last N days", "Flights that landed in X" |
| **Analysis** | Run analysis functions on data | "Course quality analysis", "Anomaly detection" |
| **Aggregation** | Group, count, compute statistics | "Count by airline", "Average altitude" |
| **Output / Display** | Present results visually | "Results table", "Map view", "Alert panel" |

### Parameters

Every cube input and output is a **named parameter** with the following properties:

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Unique name within the cube (e.g., `flight_ids`, `quality_type`) |
| `type` | ParamType | One of: `string`, `number`, `boolean`, `list_of_strings`, `list_of_numbers`, `json_object` |
| `required` | boolean | Whether the parameter must have a value before execution |
| `default` | any \| null | Default value if none is provided |
| `accepts_full_result` | boolean | (Input only) Whether this param can receive a Full Result connection |
| `description` | string | Human-readable description shown in the UI |

### Connections

Users wire cubes together by dragging a line from a **specific output parameter** of one cube
to a **specific input parameter** of another cube. This is parameter-level connectivity — not
just cube-to-cube.

**Special: Full Result port.** Every cube automatically exposes a "Full Result" output that
bundles all of its output parameters into a single JSON object. Any input parameter marked with
`accepts_full_result: true` can receive this bundled output.

**Type warnings.** When a user connects two parameters of incompatible types, the system
displays a visual warning on the connection edge but does not prevent it. This gives flexibility
while signaling potential issues.

### Manual Values

Any input parameter can be filled in **two ways**:

1. **Via connection** — a line from another cube's output parameter
2. **Via manual entry** — the user types or selects a value directly in the cube's UI

If both a connection and a manual value exist, the connection takes precedence at execution time.
Configuration parameters (like selecting "jamming" for a quality type) and data parameters
(like a list of flight IDs) use the **same unified param model** — there is no separate concept
of "config" vs "data" parameters.

---

## Workflow Execution

1. The user constructs a pipeline on the canvas by placing cubes and connecting parameters.
2. The user clicks the **Run** button.
3. The backend receives the full workflow graph (nodes, edges, parameter values).
4. The execution engine performs a **topological sort** to determine execution order.
5. Cubes are executed sequentially in dependency order. Each cube receives its resolved inputs
   (from connections or manual values) and produces outputs.
6. Results are collected for every cube and returned to the frontend.
7. Each cube on the canvas updates to show its individual results (expandable panel).
   Dedicated **Output/Display cubes** provide richer visualizations (tables, charts, maps).

---

## Persistence & Workflow Management

- Workflows are **saved to PostgreSQL** when the user explicitly clicks "Save".
- Each saved workflow stores the full graph state: node positions, cube types, parameter values,
  and edge connections — serialized as JSON.
- A **workflow dashboard** lets users:
  - View a list of all saved workflows
  - Open a workflow to edit on the canvas
  - Rename a workflow
  - Delete a workflow

---

## Cube Registry

New cube types are added **by developers in Python code**. There is no admin UI for creating
cube types. The process is:

1. Create a new Python class that extends `BaseCube`.
2. Define the cube's `CubeDefinition` (name, category, input/output parameters).
3. Implement the `execute()` method with the cube's logic.
4. Place the file in the `backend/app/cubes/` directory.
5. The registry auto-discovers it at startup and adds it to the catalog.

The frontend fetches the catalog from `GET /cubes/catalog` and renders available cubes in the
sidebar.

---

## UI Layout

```
+-----------------------------------------------------------------------+
|  [Toolbar: Run | Save | Load | Workflow Name]                         |
+------+----------------------------------------------------------------+
|      |                                                                |
| Cube |                                                                |
| Cat- |                    React Flow Canvas                           |
| alog |                                                                |
| Side |       [Cube A] ---param---> [Cube B] ---param---> [Cube C]     |
| bar  |                                                                |
|      |                                                                |
|(coll-|                                                                |
| apsi-|                                                                |
| ble) |                                                                |
+------+----------------------------------------------------------------+
```

- **Full-screen canvas** with React Flow for the node editor
- **Collapsible sidebar** (left) with the cube catalog grouped by category
- **Toolbar** (top) with Run, Save, workflow name, and navigation to the dashboard
- Cubes are dragged from the sidebar onto the canvas

---

## Walkthrough Example

**Goal:** Find all flights that landed in Israel in the last day and had GPS jamming.

1. Drag a **"Middle East Flights"** cube (Data Source) onto the canvas.
   - No inputs needed — it queries all flights in the region.
   - Output params: `flight_ids` (list_of_strings), `flight_metadata` (json_object).

2. Drag a **"Filter by Landing & Time"** cube (Filter) onto the canvas.
   - Input params: `flight_ids` (list_of_strings), `country` (string), `days_back` (number).
   - Connect `flight_ids` output of cube 1 → `flight_ids` input of cube 2.
   - Manually set `country` = "Israel", `days_back` = 1.
   - Output params: `filtered_flight_ids` (list_of_strings).

3. Drag a **"Course Quality Analysis"** cube (Analysis) onto the canvas.
   - Input params: `flight_ids` (list_of_strings), `quality_type` (string).
   - Connect `filtered_flight_ids` output of cube 2 → `flight_ids` input of cube 3.
   - Manually set `quality_type` = "jamming".
   - Output params: `results` (json_object), `flagged_flights` (list_of_strings).

4. Click **Run**. The pipeline executes cubes 1 → 2 → 3 in order.

5. Each cube shows its results. Cube 3 displays the list of flights with jamming events.
   Optionally, add an **Output/Display cube** for a richer table or map view.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cubes/catalog` | List all registered cube types with full definitions |
| `POST` | `/workflows` | Create and save a new workflow |
| `GET` | `/workflows` | List all saved workflows (summary: id, name, timestamps) |
| `GET` | `/workflows/{id}` | Load a specific workflow (full graph JSON) |
| `PUT` | `/workflows/{id}` | Update a workflow (rename, edit graph) |
| `DELETE` | `/workflows/{id}` | Delete a workflow |
| `POST` | `/workflows/{id}/run` | Execute a workflow and return per-cube results |

---

## Data Model

### `workflows` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `name` | VARCHAR(255) | User-given workflow name |
| `graph_json` | JSONB | Full workflow state (nodes, edges, param values, positions) |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last modification timestamp |
