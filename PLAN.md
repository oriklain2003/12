# Project 12 — Implementation Plan

This document is the phased roadmap for building Project 12. Each phase builds on the previous
one. Phases are ordered so that the system is testable as early as possible.

---

## Phase 1 — Cube Schema & Core Types

**Goal:** Define the foundational data contracts that every part of the system depends on.

### Backend (Python / Pydantic)

**File: `backend/app/schemas/cube.py`**

```python
from enum import Enum
from typing import Any
from pydantic import BaseModel


class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST_OF_STRINGS = "list_of_strings"
    LIST_OF_NUMBERS = "list_of_numbers"
    JSON_OBJECT = "json_object"


class CubeCategory(str, Enum):
    DATA_SOURCE = "data_source"
    FILTER = "filter"
    ANALYSIS = "analysis"
    AGGREGATION = "aggregation"
    OUTPUT = "output"


class ParamDefinition(BaseModel):
    name: str
    type: ParamType
    required: bool = True
    default: Any | None = None
    accepts_full_result: bool = False
    description: str = ""


class CubeDefinition(BaseModel):
    id: str
    name: str
    category: CubeCategory
    description: str = ""
    icon: str = "cube"
    input_params: list[ParamDefinition] = []
    output_params: list[ParamDefinition] = []
```

**File: `backend/app/cubes/base.py`**

```python
from abc import ABC, abstractmethod
from typing import Any
from app.schemas.cube import CubeDefinition


class BaseCube(ABC):
    definition: CubeDefinition

    @abstractmethod
    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Receive resolved input values keyed by param name.
        Return output values keyed by param name.
        """
        ...
```

### Frontend (TypeScript)

**File: `frontend/src/types/cube.ts`**

```typescript
export type ParamType =
  | "string"
  | "number"
  | "boolean"
  | "list_of_strings"
  | "list_of_numbers"
  | "json_object";

export type CubeCategory =
  | "data_source"
  | "filter"
  | "analysis"
  | "aggregation"
  | "output";

export interface ParamDefinition {
  name: string;
  type: ParamType;
  required: boolean;
  default?: any;
  accepts_full_result: boolean;
  description: string;
}

export interface CubeDefinition {
  id: string;
  name: string;
  category: CubeCategory;
  description: string;
  icon: string;
  input_params: ParamDefinition[];
  output_params: ParamDefinition[];
}
```

**File: `frontend/src/types/workflow.ts`**

```typescript
export interface WorkflowSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowNode {
  id: string;
  cube_id: string;
  position: { x: number; y: number };
  param_values: Record<string, any>;
}

export interface WorkflowEdge {
  id: string;
  source_node_id: string;
  source_param: string;
  target_node_id: string;
  target_param: string;
}

export interface Workflow {
  id: string;
  name: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: string;
  updated_at: string;
}

export interface CubeResult {
  node_id: string;
  status: "success" | "error";
  outputs: Record<string, any>;
  error?: string;
}

export interface WorkflowRunResult {
  workflow_id: string;
  results: Record<string, CubeResult>;
}
```

### Deliverables

- [ ] `backend/app/schemas/cube.py` — ParamType, CubeCategory, ParamDefinition, CubeDefinition
- [ ] `backend/app/cubes/base.py` — BaseCube abstract class
- [ ] `frontend/src/types/cube.ts` — TypeScript mirror of cube schemas
- [ ] `frontend/src/types/workflow.ts` — Workflow, WorkflowNode, WorkflowEdge, run result types

---

## Phase 2 — Backend Foundation

**Goal:** Stand up the FastAPI server with cube registry, workflow CRUD, and execution engine.

### 2.1 Project Scaffold

```
backend/
  requirements.txt        # fastapi, uvicorn, sqlalchemy, asyncpg, pydantic
  app/
    __init__.py
    main.py                # FastAPI app, CORS, router includes, startup events
    config.py              # DB URL, settings
    database.py            # SQLAlchemy async engine & session
```

### 2.2 Cube Registry

**File: `backend/app/engine/registry.py`**

- `CubeRegistry` class with a dict mapping `cube_id -> BaseCube` instance.
- `register(cube: BaseCube)` method.
- `get_catalog() -> list[CubeDefinition]` returns definitions for all registered cubes.
- Auto-discovery: on startup, import all modules in `app/cubes/` and register them.

### 2.3 Workflow DB Model

**File: `backend/app/models/workflow.py`**

- SQLAlchemy model for the `workflows` table.
- Columns: `id` (UUID), `name` (String), `graph_json` (JSONB), `created_at`, `updated_at`.

**File: `backend/app/schemas/workflow.py`**

- Pydantic schemas: `WorkflowCreate`, `WorkflowUpdate`, `WorkflowResponse`, `WorkflowSummary`.

### 2.4 API Endpoints

**File: `backend/app/routers/cubes.py`**

| Endpoint | Handler |
|----------|---------|
| `GET /cubes/catalog` | Return `registry.get_catalog()` |

**File: `backend/app/routers/workflows.py`**

| Endpoint | Handler |
|----------|---------|
| `POST /workflows` | Create workflow, store graph_json |
| `GET /workflows` | List all workflows (id, name, timestamps) |
| `GET /workflows/{id}` | Load full workflow |
| `PUT /workflows/{id}` | Update name and/or graph_json |
| `DELETE /workflows/{id}` | Delete workflow |
| `POST /workflows/{id}/run` | Execute workflow, return results |

### 2.5 Execution Engine

**File: `backend/app/engine/executor.py`**

- `WorkflowExecutor` class.
- `execute(graph_json, registry) -> dict[node_id, CubeResult]`.
- Steps:
  1. Parse the graph JSON into nodes and edges.
  2. Build a dependency graph from edges.
  3. Topological sort to get execution order.
  4. For each node in order:
     a. Resolve inputs: for each input param, check if an edge provides a value from a
        previous node's output; otherwise use the manual value.
     b. Look up the cube type in the registry.
     c. Call `cube.execute(resolved_inputs)`.
     d. Store outputs keyed by node ID.
  5. Return all results.

### 2.6 Example Stub Cubes

**File: `backend/app/cubes/examples/echo_cube.py`**

- Takes any `json_object` input, returns it unchanged. For testing the pipeline.

**File: `backend/app/cubes/examples/filter_stub.py`**

- Takes `items` (list_of_strings) and `contains` (string), returns filtered list.

### Deliverables

- [ ] FastAPI project scaffold with CORS, config, database setup
- [ ] `CubeRegistry` with auto-discovery
- [ ] `workflows` SQLAlchemy model + Pydantic schemas
- [ ] Cubes router (`GET /cubes/catalog`)
- [ ] Workflows router (full CRUD + run)
- [ ] `WorkflowExecutor` with topological sort
- [ ] 2 example stub cubes

---

## Phase 3 — Frontend Foundation

**Goal:** Build the React Flow canvas with custom cube nodes, parameter handles, and the
cube catalog sidebar.

### 3.1 Project Scaffold

```
frontend/
  package.json             # react, react-dom, reactflow, zustand, typescript
  tsconfig.json
  vite.config.ts
  index.html
  src/
    main.tsx
    App.tsx
```

### 3.2 API Client

**File: `frontend/src/api/client.ts`**

- Thin fetch wrapper with base URL config, JSON parsing, error handling.

**File: `frontend/src/api/cubes.ts`**

- `getCatalog(): Promise<CubeDefinition[]>`

**File: `frontend/src/api/workflows.ts`**

- `listWorkflows()`, `getWorkflow(id)`, `createWorkflow(data)`,
  `updateWorkflow(id, data)`, `deleteWorkflow(id)`, `runWorkflow(id, graph)`

### 3.3 Zustand Store

**File: `frontend/src/store/flowStore.ts`**

- Holds React Flow nodes and edges.
- Actions: `addNode`, `removeNode`, `updateNodeParamValue`, `onNodesChange`, `onEdgesChange`,
  `onConnect`, `setResults`, `clearResults`, `resetFlow`, `loadFlow`.
- Serialization helpers: `toWorkflowJSON()`, `fromWorkflowJSON()`.

### 3.4 Custom CubeNode Component

**File: `frontend/src/components/CubeNode/CubeNode.tsx`**

The custom React Flow node renders:

```
+------------------------------------------+
|  [icon] Cube Name              [status]  |
|  category label                          |
+------------------------------------------+
|  IN                          OUT         |
|  o param_a (string)    result_x o        |
|  o param_b (number)    result_y o        |
|                        [Full Result] o   |
+------------------------------------------+
|  [v] Results (expandable)                |
|  { ... JSON preview ... }                |
+------------------------------------------+
```

- Left-side **Handle** for each input param, labeled with name and type.
- Right-side **Handle** for each output param + the special Full Result handle.
- Input params show an inline editable field (text input, number input, toggle, or JSON editor
  depending on type) that is visible when the param has no incoming connection.
- Status indicator: idle (gray), running (blue pulse), success (green), error (red).
- Expandable results panel at the bottom showing execution output.

**File: `frontend/src/components/CubeNode/ParamHandle.tsx`**

- Renders a single React Flow Handle with label. Color-coded by param type.

**File: `frontend/src/components/CubeNode/ParamField.tsx`**

- Inline editor for manual param values. Renders the appropriate input control based on
  ParamType. Hidden when an edge is connected to this param.

**File: `frontend/src/components/CubeNode/ResultsPanel.tsx`**

- Collapsible panel showing the cube's execution results as formatted JSON.

### 3.5 Canvas

**File: `frontend/src/components/Canvas/FlowCanvas.tsx`**

- React Flow `<ReactFlow>` wrapper with:
  - Custom node type registration (`cubeNode` → `CubeNode`).
  - Background grid, controls, minimap.
  - Drop handler for adding cubes from the sidebar.
  - Connection validation callback: warn on type mismatch (highlight edge in orange).

### 3.6 Sidebar — Cube Catalog

**File: `frontend/src/components/Sidebar/CubeCatalog.tsx`**

- Fetches catalog from API on mount.
- Groups cubes by category with collapsible sections.
- Each cube entry is draggable (sets drag data for the canvas drop handler).
- Search/filter input at the top.

### 3.7 Toolbar

**File: `frontend/src/components/Toolbar/Toolbar.tsx`**

- **Run** button — serializes the flow and calls `POST /workflows/{id}/run`.
- **Save** button — serializes the flow and calls save API.
- **Workflow name** — editable text field.
- **Dashboard** link — navigates to the workflow list.

### Deliverables

- [ ] Vite + React + TypeScript project scaffold
- [ ] API client layer (cubes + workflows)
- [ ] Zustand flow store with serialization
- [ ] `CubeNode` custom node with param handles, inline fields, results panel
- [ ] `FlowCanvas` with drop-to-add, connection validation
- [ ] `CubeCatalog` sidebar (grouped, draggable, searchable)
- [ ] `Toolbar` with Run, Save, name edit, dashboard link

---

## Phase 4 — Workflow Management

**Goal:** Save, load, and manage workflows via the dashboard.

### 4.1 Dashboard Page

**File: `frontend/src/components/Dashboard/WorkflowList.tsx`**

- Lists all saved workflows with name, created date, last updated.
- Actions per row: Open, Rename (inline edit), Delete (with confirmation).
- "New Workflow" button.
- This is a separate view/page (not overlay on the canvas).

### 4.2 Routing

- Simple client-side routing (React Router or equivalent):
  - `/` → Workflow dashboard
  - `/workflow/:id` → Canvas editor for a specific workflow
  - `/workflow/new` → Empty canvas for a new workflow

### 4.3 Serialization

- `toWorkflowJSON()` in the store converts React Flow state (nodes with positions, param
  values, edges with source/target param info) into the backend's expected JSON format.
- `fromWorkflowJSON()` does the reverse when loading a saved workflow.

### Deliverables

- [ ] Workflow dashboard page with list, create, rename, delete
- [ ] Client-side routing (dashboard ↔ canvas editor)
- [ ] Serialization/deserialization between React Flow state and API format

---

## Phase 5 — Execution & Results

**Goal:** Wire the Run button to the backend, display per-cube results on the canvas.

### 5.1 Run Flow

1. User clicks **Run**.
2. Frontend serializes the current flow into the workflow graph JSON.
3. `POST /workflows/{id}/run` sends the graph to the backend.
4. Backend `WorkflowExecutor` processes the graph and returns per-node results.
5. Frontend receives the response and updates each node's `results` and `status` in the store.
6. `CubeNode` components re-render with their results visible.

### 5.2 Status Updates

- Before execution: all nodes set to `running`.
- On response: each node set to `success` or `error` based on its individual result.
- Error nodes display the error message in their results panel.

### 5.3 Edge Cases

- Cycles in the graph: detected during topological sort, return an error before execution.
- Missing required params: validation before execution, return errors for affected nodes.
- Cube execution failure: catch per-cube, mark that node as error, continue or stop
  (configurable — default: stop on first error).

### Deliverables

- [ ] Run button integration (serialize → API call → update store)
- [ ] Per-cube status indicators (running/success/error)
- [ ] Per-cube results display in CubeNode
- [ ] Error handling: cycles, missing params, cube failures

---

## Phase 6 — Polish & Example Cubes

**Goal:** Refine the UX, add example cubes for each category, write the developer guide.

### 6.1 Example Stub Cubes

One per category, with realistic definitions but stub implementations:

| Cube | Category | Inputs | Outputs |
|------|----------|--------|---------|
| Middle East Flights | data_source | (none) | flight_ids, flight_metadata |
| Filter by Criteria | filter | flight_ids, country, days_back | filtered_flight_ids |
| Course Quality | analysis | flight_ids, quality_type | results, flagged_flights |
| Count by Field | aggregation | items, group_by_field | counts |
| Results Table | output | data | (display only) |

### 6.2 Developer Guide

A section in the README or a `CONTRIBUTING.md` explaining:

1. How to create a new cube (extend BaseCube, define CubeDefinition, implement execute).
2. Where to place the file (`backend/app/cubes/`).
3. How auto-discovery works.
4. How to test a cube in isolation.

### 6.3 UI Polish

- Keyboard shortcuts: Delete (remove selected), Ctrl+S (save), Ctrl+Enter (run).
- Zoom controls and minimap (React Flow built-ins).
- Undo/redo for node operations.
- Connection edge styling: normal (solid), type-mismatch warning (dashed orange).
- Responsive sidebar collapse/expand.

### Deliverables

- [ ] 5 example stub cubes (one per category)
- [ ] Developer guide for adding new cubes
- [ ] Keyboard shortcuts
- [ ] Edge styling for type-mismatch warnings
- [ ] General UI polish

---

## Project Structure

```
12-flow/
  CONVERSATION.md                # Planning session transcript
  PROJECT.md                     # Project specification
  PLAN.md                        # This file

  frontend/
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      types/
        cube.ts                  # ParamType, ParamDefinition, CubeDefinition
        workflow.ts              # Workflow, WorkflowNode, WorkflowEdge, run results
      api/
        client.ts                # Fetch wrapper
        cubes.ts                 # getCatalog()
        workflows.ts             # CRUD + run
      components/
        Canvas/
          FlowCanvas.tsx         # React Flow wrapper with drop & validation
        CubeNode/
          CubeNode.tsx           # Custom node component
          ParamHandle.tsx        # Single param handle (input/output)
          ParamField.tsx         # Inline manual value editor
          ResultsPanel.tsx       # Expandable results on cube
        Sidebar/
          CubeCatalog.tsx        # Cube catalog grouped by category
        Dashboard/
          WorkflowList.tsx       # Saved workflows list
        Toolbar/
          Toolbar.tsx            # Run, Save, name, dashboard link
      store/
        flowStore.ts             # Zustand store for flow state

  backend/
    requirements.txt
    app/
      __init__.py
      main.py                    # FastAPI entry point
      config.py                  # Settings / env vars
      database.py                # SQLAlchemy engine & session
      models/
        __init__.py
        workflow.py              # Workflow SQLAlchemy model
      schemas/
        __init__.py
        cube.py                  # Pydantic: ParamType, ParamDefinition, CubeDefinition
        workflow.py              # Pydantic: Workflow request/response schemas
      routers/
        __init__.py
        cubes.py                 # GET /cubes/catalog
        workflows.py             # Workflow CRUD + run endpoints
      engine/
        __init__.py
        registry.py              # CubeRegistry with auto-discovery
        executor.py              # WorkflowExecutor (topo sort + execute)
      cubes/
        __init__.py              # Auto-discovery loader
        base.py                  # BaseCube abstract class
        examples/
          __init__.py
          echo_cube.py           # Pass-through test cube
          filter_stub.py         # Stub filter cube
          middle_east_flights.py # Stub data source cube
          course_quality.py      # Stub analysis cube
          results_table.py       # Stub output cube
```

---

## Execution Order Summary

```
Phase 1  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5  →  Phase 6
 Types      Backend     Frontend     Workflows    Run &       Polish
 & Schema   API +       Canvas +     Dashboard    Results
            Engine      Nodes
```

Each phase produces a working, testable increment. After Phase 3, the full loop (build flow →
save → load → run → see results) is achievable.
