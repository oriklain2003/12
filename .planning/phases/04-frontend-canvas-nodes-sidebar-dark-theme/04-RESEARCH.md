# Phase 4: Frontend Canvas, Nodes, Sidebar & Dark Theme - Research

**Researched:** 2026-03-03
**Domain:** React Flow v12, Zustand v5, CSS glassmorphism, drag-and-drop canvas
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Dark theme with CSS custom properties for the entire app
- Liquid glass effect on nodes — find a well-regarded implementation from GitHub/open-source libraries (backdrop-filter blur + saturation approach from ROADMAP)
- Simple types (string, number, boolean): standard inputs (text, number, checkbox)
- Complex types (list_of_strings, list_of_numbers, json_object): research online solutions for compact input widgets — must not dominate the node or take excessive canvas space
- Editors should be compact — roughly a third of the node height at most
- Drag initiation via a drag handle on each cube card (not the entire card)
- Collapsed state shows as an icon strip (not fully hidden)
- Search input filters cubes by name inclusion (substring match)
- Grouped by CubeCategory as specified in requirements
- Solid lines for valid connections (not animated or gradient)
- Straight edge routing (not bezier or step)
- Type mismatch: dashed orange edge with warning (per FRONT-12)
- Full Result incompatibility: error toast when user attempts to connect Full Result to an input without accepts_full_result=true — connection prevented
- Color-coded handles by ParamType as specified (FRONT-05)

### Claude's Discretion
- Category visual differentiation approach (color scheme, icons, header styling)
- Exact dark theme color palette and CSS variable naming
- Liquid glass library/implementation choice
- Complex type input widget selection (tag inputs, textareas, JSON editors, etc.)
- How "hidden when connected" is visually communicated on the node
- Zustand store internal structure and action design
- API client error handling patterns
- Toolbar layout and styling
- Results preview compact layout on nodes

### Deferred Ideas (OUT OF SCOPE)
- Workflow save/load and dashboard — Phase 5
- SSE execution with live status indicators on nodes — Phase 5
- Keyboard shortcuts (Ctrl+S, Ctrl+Enter, Delete) — Phase 5
- Results drawer with table + map — Phase 6
- Polygon drawing UI on canvas — future phase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FRONT-02 | Dark theme CSS with CSS custom properties and liquid glass effects (backdrop-filter: blur(12px) saturate(150%)) | CSS variables section + glassmorphism pattern |
| FRONT-03 | React Flow canvas with dark background, grid, pan/zoom, and drop handler for adding cubes | React Flow Background, colorMode, onDrop, onDragOver patterns |
| FRONT-04 | Custom CubeNode component rendering cube name, category icon, input handles (left), output handles + Full Result (right) | NodeProps<T>, Handle with id, Position |
| FRONT-05 | Parameter handles color-coded by ParamType (string=blue, number=green, boolean=orange, flight_ids=purple, json=gray, arrays=teal) | Handle style prop pattern |
| FRONT-06 | Inline parameter editors on each CubeNode — text inputs, number inputs, checkboxes — hidden when a connection provides the value | Zustand store connected edge detection, conditional render |
| FRONT-07 | Compact results preview panel on each CubeNode showing row count and first few values | Component design inside custom node |
| FRONT-08 | Collapsible cube catalog sidebar grouped by CubeCategory, each cube draggable onto canvas, with search/filter input, toggle button | HTML DnD API + onDrop/screenToFlowPosition pattern |
| FRONT-09 | Zustand store managing nodes, edges, cube catalog, execution status, results, with JSON serialization | Zustand v5 create<T>()() + applyNodeChanges/applyEdgeChanges |
| FRONT-10 | Toolbar with Run button, Save button, editable workflow name field, and link back to dashboard | Component design, deferred functional hooks |
| FRONT-11 | API client module (fetch wrapper) for all backend endpoints with error handling | Fetch wrapper pattern with base URL |
| FRONT-12 | Connection validation — type mismatch as dashed orange edge, Full Result only to accepts_full_result inputs | isValidConnection + onConnect + custom edge type |
</phase_requirements>

---

## Summary

Phase 4 constructs the complete visual editor: a React Flow v12 canvas with custom cube nodes, a collapsible sidebar catalog, Zustand v5 state management, an API client layer, and a dark glass aesthetic. All core libraries are already installed (`@xyflow/react ^12.10.1`, `zustand ^5.0.11`) and the Vite proxy to the backend is in place.

The primary technical challenges are: (1) correctly bridging Zustand state with React Flow's change-handler system (`applyNodeChanges`/`applyEdgeChanges`), (2) implementing connection validation logic in `isValidConnection` that reads handle metadata from the Zustand store's cube catalog, and (3) rendering compact inline param editors that hide when a connection supplies the value. The glassmorphism styling is well-understood CSS — no additional library is needed.

**Primary recommendation:** Build the Zustand store first as the central contract; then implement React Flow integration; then build individual node/sidebar components against the store; add CSS theming last.

---

## Standard Stack

### Core (already installed — no new installs for these)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @xyflow/react | ^12.10.1 | Node-based canvas, custom nodes, handles, edges | Industry standard for node-graph UI in React |
| zustand | ^5.0.11 | Global state for nodes, edges, catalog, results | React Flow's own internal state uses Zustand; natural fit |
| react | ^19.2.0 | UI framework | Project baseline |
| typescript | ~5.9.3 | Type safety | Project baseline |
| vite | ^7.3.1 | Dev server + HMR | Project baseline |

### Supporting (install as needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sonner | latest | Error/warning toast notifications | Needed for FRONT-12 Full Result rejection toast |
| react-tag-input-component | latest | Compact tag input for list_of_strings / list_of_numbers params | Claude's discretion — lightweight, typed, small footprint |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sonner | react-hot-toast | Both ~5KB, zero deps, dark theme; sonner has broader ecosystem adoption (shadcn/ui standard) |
| react-tag-input-component | Custom tag input | Custom is ~20 lines but requires handling keyboard events, paste, delete — not worth it |
| CSS glassmorphism (custom) | GlassiFy library | GlassiFy adds SVG turbulence; pure CSS is sufficient for this use case |

**Installation (new dependencies only):**
```bash
cd frontend && pnpm add sonner react-tag-input-component
```

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── styles/
│   ├── theme.css           # CSS custom properties (dark palette, --color-*)
│   └── glass.css           # .glass utility class (backdrop-filter)
├── api/
│   ├── client.ts           # fetch wrapper with base URL + error handling
│   ├── cubes.ts            # getCatalog(): CubeDefinition[]
│   └── workflows.ts        # getWorkflow, createWorkflow, updateWorkflow (stubs for Phase 5)
├── store/
│   └── flowStore.ts        # Zustand store — all shared state + actions
├── components/
│   ├── Canvas/
│   │   └── FlowCanvas.tsx  # ReactFlow wrapper, onDrop, onDragOver, nodeTypes, edgeTypes
│   ├── CubeNode/
│   │   ├── CubeNode.tsx        # Custom node component (NodeProps<CubeFlowNode>)
│   │   ├── ParamHandle.tsx     # Single colored Handle by ParamType
│   │   ├── ParamField.tsx      # Inline editor (hidden when connected)
│   │   └── ResultsPanel.tsx    # Compact row count + preview
│   ├── Sidebar/
│   │   └── CubeCatalog.tsx     # Category groups, drag handles, search
│   └── Toolbar/
│       └── Toolbar.tsx         # Run, Save (stub), workflow name, dashboard link
└── App.tsx                     # Layout shell: sidebar + canvas + toolbar
```

### Pattern 1: React Flow Node Type System (TypeScript)

**What:** Define a typed union of custom node types so React Flow and TypeScript agree on node data shapes.
**When to use:** Before writing any node component.

```typescript
// Source: https://reactflow.dev/learn/advanced-use/typescript
import type { Node, BuiltInNode } from '@xyflow/react';
import type { CubeDefinition } from '../types/cube';

export type CubeNodeData = {
  cube_id: string;
  cubeDef: CubeDefinition;         // resolved from catalog at add-time
  params: Record<string, unknown>; // user-entered values
};

// The node type must use `type`, not `interface`, for Node<> generic
export type CubeFlowNode = Node<CubeNodeData, 'cube'>;

// Union if we ever add more node types:
export type AppNode = CubeFlowNode | BuiltInNode;
```

**Key v12 rule:** `node.width` / `node.height` are user-set fixed dimensions; measured dimensions live in `node.measured.width` / `node.measured.height`.

### Pattern 2: Zustand + React Flow Integration Store

**What:** Single Zustand store holds all state; React Flow consumes it via `onNodesChange`, `onEdgesChange`, `onConnect` handlers.
**When to use:** This is the authoritative state layer — React Flow is a view layer only.

```typescript
// Source: https://reactflow.dev/learn/advanced-use/state-management
import { create } from 'zustand';
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type NodeChange,
  type EdgeChange,
  type Connection,
  type Edge,
} from '@xyflow/react';
import type { CubeDefinition } from '../types/cube';
import type { CubeFlowNode } from './types';

interface FlowState {
  nodes: CubeFlowNode[];
  edges: Edge[];
  catalog: CubeDefinition[];
  results: Record<string, unknown>;
  setCatalog: (catalog: CubeDefinition[]) => void;
  onNodesChange: (changes: NodeChange<CubeFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addCubeNode: (cubeId: string, position: { x: number; y: number }) => void;
  updateNodeParam: (nodeId: string, paramName: string, value: unknown) => void;
}

export const useFlowStore = create<FlowState>()((set, get) => ({
  nodes: [],
  edges: [],
  catalog: [],
  results: {},
  setCatalog: (catalog) => set({ catalog }),
  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),
  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),
  onConnect: (connection) =>
    set({ edges: addEdge(connection, get().edges) }),
  addCubeNode: (cubeId, position) => {
    const cubeDef = get().catalog.find((c) => c.id === cubeId);
    if (!cubeDef) return;
    const newNode: CubeFlowNode = {
      id: crypto.randomUUID(),
      type: 'cube',
      position,
      data: { cube_id: cubeId, cubeDef, params: {} },
    };
    set({ nodes: [...get().nodes, newNode] });
  },
  updateNodeParam: (nodeId, paramName, value) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, params: { ...n.data.params, [paramName]: value } } }
          : n
      ),
    }),
}));
```

**Critical:** Zustand store actions must NOT use `useReactFlow()` hook — hooks are React-context bound. `screenToFlowPosition` must be called inside a component that renders inside `<ReactFlow>`.

### Pattern 3: Drag-and-Drop (Sidebar → Canvas)

**What:** HTML5 DnD API on sidebar cards; `onDrop` + `onDragOver` on the ReactFlow wrapper; `screenToFlowPosition` converts coordinates.
**When to use:** Adding cubes from sidebar to canvas.

```typescript
// Source: https://reactflow.dev/examples/interaction/drag-and-drop
// In CubeCatalog.tsx (sidebar)
const onDragStart = (event: DragEvent<HTMLDivElement>, cubeId: string) => {
  event.dataTransfer.setData('application/cube-id', cubeId);
  event.dataTransfer.effectAllowed = 'move';
};

// In FlowCanvas.tsx (must be inside <ReactFlow> provider to access useReactFlow)
const { screenToFlowPosition } = useReactFlow();

const onDrop = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  const cubeId = event.dataTransfer.getData('application/cube-id');
  if (!cubeId) return;
  const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
  addCubeNode(cubeId, position);  // calls store action
}, [screenToFlowPosition, addCubeNode]);

const onDragOver = useCallback((event: React.DragEvent) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
}, []);
```

**The drag handle constraint:** In the sidebar, only attach `draggable` + `onDragStart` to the drag handle element, not the entire card. Use `e.stopPropagation()` in the card's click handlers.

### Pattern 4: Custom Node with Multiple Typed Handles

**What:** CubeNode renders input params as target handles (left) and output params as source handles (right), each with a unique ID.
**When to use:** Rendering every cube on the canvas.

```typescript
// Source: https://reactflow.dev/learn/customization/handles
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { CubeFlowNode } from '../../store/types';

export function CubeNode({ data, isConnectable }: NodeProps<CubeFlowNode>) {
  const { cubeDef, params } = data;
  return (
    <div className="cube-node glass">
      <div className="cube-node__header">{cubeDef.name}</div>
      {cubeDef.inputs.map((param) => (
        <div key={param.name} className="cube-node__param">
          <Handle
            type="target"
            position={Position.Left}
            id={param.name}              // handle ID = param name
            style={{ background: PARAM_COLORS[param.type] }}
            isConnectable={isConnectable}
            isValidConnection={isValidForHandle(param)}
          />
          <ParamField param={param} nodeId={data.cube_id} value={params[param.name]} />
        </div>
      ))}
      {cubeDef.outputs.map((param) => (
        <Handle
          key={param.name}
          type="source"
          position={Position.Right}
          id={param.name}
          style={{ background: PARAM_COLORS[param.type] }}
          isConnectable={isConnectable}
        />
      ))}
      {/* Full Result handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="__full_result__"
        style={{ background: PARAM_COLORS['json'] }}
        isConnectable={isConnectable}
      />
    </div>
  );
}
```

**Handle IDs:** The `id` on each `<Handle>` becomes the `sourceHandle` / `targetHandle` on edges. This is how `isValidConnection` identifies which param is being connected.

### Pattern 5: Connection Validation (FRONT-12)

**What:** `isValidConnection` on `<ReactFlow>` prevents Full Result connections to non-accepting params. Custom edge type shows dashed orange for type mismatches.
**When to use:** Enforcing typed connections.

```typescript
// Source: https://reactflow.dev/api-reference/types/is-valid-connection
const isValidConnection = useCallback((connection: Connection): boolean => {
  const { sourceHandle, targetHandle, target } = connection;
  const targetNode = useFlowStore.getState().nodes.find((n) => n.id === target);
  if (!targetNode) return false;
  const targetParam = targetNode.data.cubeDef.inputs.find(
    (p) => p.name === targetHandle
  );
  if (!targetParam) return false;
  // Full Result can only connect to params with accepts_full_result: true
  if (sourceHandle === '__full_result__' && !targetParam.accepts_full_result) {
    toast.error('This input does not accept Full Result');
    return false;
  }
  return true;  // type mismatches allowed but shown as dashed orange edge
}, []);

// onConnect: add edge with type='mismatch' when ParamType differs
const onConnect = useCallback((connection: Connection) => {
  const { sourceHandle, targetHandle, source, target } = connection;
  // resolve source param type and target param type from catalog
  const isMismatch = resolveTypeMismatch(connection, nodes, catalog);
  const edge: Edge = {
    ...connection,
    id: `${source}-${sourceHandle}-${target}-${targetHandle}`,
    type: isMismatch ? 'mismatch' : 'straight',
    style: isMismatch ? undefined : { stroke: '#6b7280' },
  };
  setEdges((eds) => [...eds, edge]);
}, [nodes, catalog]);
```

**Custom mismatch edge type:**

```typescript
// components/Canvas/MismatchEdge.tsx
import { getStraightPath, BaseEdge, type EdgeProps } from '@xyflow/react';

export function MismatchEdge({ id, sourceX, sourceY, targetX, targetY }: EdgeProps) {
  const [edgePath] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{ stroke: '#f97316', strokeDasharray: '6 3' }}
    />
  );
}
```

### Pattern 6: Dark Theme + Liquid Glass CSS

**What:** CSS custom properties on `:root` for the dark palette; `.glass` utility class for nodes.
**When to use:** Global in `theme.css` and `glass.css`; apply `colorMode="dark"` on `<ReactFlow>`.

```css
/* theme.css */
:root {
  --color-bg:        #0f1117;
  --color-surface:   #1a1d27;
  --color-border:    rgba(255, 255, 255, 0.08);
  --color-text:      rgba(255, 255, 255, 0.87);
  --color-text-dim:  rgba(255, 255, 255, 0.45);
  --color-accent:    #6366f1;  /* indigo — Claude's discretion */
  --color-orange:    #f97316;  /* mismatch edges */

  /* React Flow CSS variable overrides */
  --xy-background-color: var(--color-bg);
  --xy-node-background-color-default: transparent;
  --xy-node-border-default: 1px solid var(--color-border);
  --xy-edge-stroke-default: #4b5563;
}
```

```css
/* glass.css — Source: https://www.joshwcomeau.com/css/backdrop-filter/ */
.glass {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(12px) saturate(150%);
  -webkit-backdrop-filter: blur(12px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}
```

**React Flow dark integration:**
```tsx
import '@xyflow/react/dist/style.css';
// Then in FlowCanvas.tsx:
<ReactFlow colorMode="dark" ... />
```

### Pattern 7: nodeTypes Must Be Defined Outside Component

**What:** `nodeTypes` and `edgeTypes` objects must be defined outside the component render function to avoid React Flow emitting a warning and triggering unnecessary re-renders.

```typescript
// Defined at module level — NEVER inside a React component or render function
const nodeTypes = { cube: CubeNode } as const;
const edgeTypes = { mismatch: MismatchEdge } as const;

export function FlowCanvas() {
  return <ReactFlow nodeTypes={nodeTypes} edgeTypes={edgeTypes} ... />;
}
```

### Anti-Patterns to Avoid

- **Calling `useReactFlow()` in Zustand store actions:** Not possible — hooks require React context. Keep `screenToFlowPosition` in the component that renders inside `<ReactFlow>`.
- **Defining `nodeTypes` inside the component body:** React Flow detects this and warns. Always define at module level or use `useMemo`.
- **Using `node.width` / `node.height` for measured sizes:** In v12, measured sizes are in `node.measured.width` / `node.measured.height`. Use these for any layout calculations.
- **Mutating node/edge objects directly:** React Flow v12 requires new object references. Always spread: `{ ...node, data: { ...node.data, ... } }`.
- **Setting `onConnect` in the store and also using `isValidConnection` on ReactFlow:** This creates double-validation confusion. Keep validation in `isValidConnection` (returns false early), keep the edge-add logic in `onConnect`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Node change application | Custom diff/merge for node position updates | `applyNodeChanges` from @xyflow/react | Handles 7+ change types (position, select, replace, remove, add, dimensions, reset) |
| Edge change application | Custom edge state update logic | `applyEdgeChanges` from @xyflow/react | Handles select/remove correctly |
| Edge creation from connection | Manual edge object construction | `addEdge` from @xyflow/react | Handles duplicate prevention and proper id generation |
| Screen→flow coordinate conversion | Manual bounding-box math | `screenToFlowPosition` from `useReactFlow()` | Accounts for zoom, pan, and scroll — math is non-trivial |
| Toast notifications | Custom toast component | `sonner` | Handles stacking, z-index, dark mode, dismiss — 5KB |
| Tag input (list_of_strings) | Custom key-press tag input | `react-tag-input-component` | Handles backspace-delete, comma-split, paste — edge cases compound |
| Straight edge path | Custom SVG path calculation | `getStraightPath` from @xyflow/react | Handles edge cases, works with BaseEdge |

**Key insight:** React Flow's utility functions (`applyNodeChanges`, `applyEdgeChanges`, `addEdge`, path helpers) exist precisely because these operations are more complex than they appear. Bypassing them leads to subtle bugs when nodes are deleted, reconnected, or when flows are large.

---

## Common Pitfalls

### Pitfall 1: nodeTypes Recreation Warning

**What goes wrong:** React Flow logs "It looks like you've created a new nodeTypes or edgeTypes object" and potentially causes performance issues.
**Why it happens:** The object is defined inside the component body, so a new reference is created on every render.
**How to avoid:** Define `const nodeTypes = { cube: CubeNode }` at module level, outside any component.
**Warning signs:** Console warning from React Flow on every render.

### Pitfall 2: useReactFlow Outside ReactFlow Provider

**What goes wrong:** Runtime error "useReactFlow: ReactFlowProvider is not mounted."
**Why it happens:** `useReactFlow()` requires access to the ReactFlow React context. Components above `<ReactFlow>` in the tree can't call it.
**How to avoid:** Only call `useReactFlow()` in components rendered as children of `<ReactFlow>` or wrapped in `<ReactFlowProvider>`. The `FlowCanvas` component itself is the right place for `screenToFlowPosition`.
**Warning signs:** Runtime error on first render.

### Pitfall 3: Handle IDs Not Matching Edge sourceHandle/targetHandle

**What goes wrong:** Connections appear to work visually but `sourceHandle` and `targetHandle` on the edge are `null` or wrong, breaking `isValidConnection` logic.
**Why it happens:** `<Handle id="param_name">` must match exactly what the edge references. If handles have no `id`, they default to null.
**How to avoid:** Always set explicit `id={param.name}` on every Handle. Verify in React DevTools that edges have non-null sourceHandle/targetHandle.
**Warning signs:** Validation logic never triggers; all connections succeed.

### Pitfall 4: v12 node.measured vs node.width

**What goes wrong:** Code reads `node.width` and gets `undefined` even after the node renders.
**Why it happens:** In v12, `node.width` / `node.height` are optional user-defined props. Measured dimensions are in `node.measured.width` / `node.measured.height`.
**How to avoid:** If you need actual rendered size, read `node.measured?.width`. If you want fixed sizing, set `node.width = 280` explicitly in the node definition.
**Warning signs:** Layout calculations or resize logic return NaN or undefined.

### Pitfall 5: Glassmorphism on Unsupported Backgrounds

**What goes wrong:** Glass nodes look flat/opaque — no blur effect visible.
**Why it happens:** `backdrop-filter` blurs what's directly behind the element. If the canvas background is a solid color with no variation, blur has nothing to reveal.
**How to avoid:** The React Flow `<Background>` with dots/lines variant creates the grid texture behind nodes, giving backdrop-filter something to work with. Use `BackgroundVariant.Lines` or `BackgroundVariant.Dots`.
**Warning signs:** Glass nodes look like solid dark panels.

### Pitfall 6: Zustand Store Import in Zustand Actions (Circular)

**What goes wrong:** Importing `useFlowStore` inside store actions causes circular dependency.
**Why it happens:** The store file imports itself.
**How to avoid:** Use `get()` inside store actions (provided by Zustand's create callback) to access current state — never import the store hook inside the store file.
**Warning signs:** Webpack circular dependency warning; store returns undefined.

### Pitfall 7: ParamField Hidden-When-Connected Requires Edge Lookup

**What goes wrong:** ParamField doesn't know if its handle is connected.
**Why it happens:** Individual params don't have direct access to edge state.
**How to avoid:** In `ParamField`, derive `isConnected` by checking if any edge in the store has `targetHandle === param.name && target === nodeId`. Use a selector: `const isConnected = useFlowStore(s => s.edges.some(e => e.target === nodeId && e.targetHandle === param.name))`.
**Warning signs:** Param fields still show when connected; user sees stale manual value alongside connected value.

---

## Code Examples

### API Client Pattern

```typescript
// frontend/src/api/client.ts
const BASE = '/api';  // proxied via Vite config to localhost:8000

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}
```

```typescript
// frontend/src/api/cubes.ts
import { apiFetch } from './client';
import type { CubeDefinition } from '../types/cube';

export const getCatalog = () => apiFetch<CubeDefinition[]>('/cubes/catalog');
```

### ParamType Handle Colors

```typescript
// Verified against FRONT-05 requirements
import { ParamType } from '../types/cube';

export const PARAM_COLORS: Record<ParamType, string> = {
  [ParamType.STRING]:       '#3b82f6',  // blue
  [ParamType.NUMBER]:       '#22c55e',  // green
  [ParamType.BOOLEAN]:      '#f97316',  // orange
  [ParamType.FLIGHT_IDS]:   '#a855f7',  // purple
  [ParamType.JSON]:         '#6b7280',  // gray
  [ParamType.STRING_ARRAY]: '#14b8a6',  // teal
  [ParamType.NUMBER_ARRAY]: '#14b8a6',  // teal
};
```

### Straight Edge as Default

```typescript
// Set straight edges as the default for all new connections
<ReactFlow
  defaultEdgeOptions={{ type: 'straight' }}
  edgeTypes={edgeTypes}
  ...
/>
```

### React Flow Background Config

```typescript
// Source: https://reactflow.dev/api-reference/components/background
import { Background, BackgroundVariant } from '@xyflow/react';

<Background
  variant={BackgroundVariant.Dots}
  gap={24}
  size={1}
  color="rgba(255,255,255,0.07)"
/>
```

### Zustand Selector to Check Connected State

```typescript
// In ParamField.tsx
const isConnected = useFlowStore(
  (s) => s.edges.some((e) => e.target === nodeId && e.targetHandle === paramName)
);
```

### Sonner Toast Setup

```typescript
// In App.tsx
import { Toaster } from 'sonner';

function App() {
  return (
    <>
      <Layout />
      <Toaster position="bottom-right" theme="dark" />
    </>
  );
}

// In validation code:
import { toast } from 'sonner';
toast.error('Full Result cannot connect to this input');
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `import ReactFlow from 'reactflow'` | `import { ReactFlow } from '@xyflow/react'` | v12 (2024) | Named exports only |
| `node.width` / `node.height` = measured | `node.measured.width` / `node.measured.height` | v12 (2024) | Breaks layout libs if not updated |
| `project()` for coordinate conversion | `screenToFlowPosition()` | v12 (2024) | No need to subtract bounds manually |
| `onEdgeUpdate` | `onReconnect` | v12 (2024) | API rename |
| `parentNode` on node | `parentId` | v12 (2024) | API rename |
| `connectionNodeId` from store | `connection.fromHandle.nodeId` | v12 (2024) | Structural change |

**Deprecated/outdated:**
- `useNodesState` / `useEdgesState`: Not deprecated, but the React Flow docs recommend Zustand for complex apps. Still usable for simpler flows.
- The `reactflow` npm package: Deprecated in favor of `@xyflow/react`. Already using the new package.

---

## Open Questions

1. **CubeDefinition `id` vs TypeScript `id`**
   - What we know: The backend's `CubeDefinition` uses `cube_id` (per STATE.md decisions). The TypeScript type in `cube.ts` has `id: string` (checked the file — it uses `id`, not `cube_id`).
   - What's unclear: There may be a field name mismatch between backend JSON (`cube_id`) and TypeScript type (`id`). Need to verify with `GET /api/cubes/catalog` response during implementation.
   - Recommendation: The API client for cubes should log the raw response on first use to confirm field name.

2. **Complex param editor for `json_object` type**
   - What we know: Must be compact. Options: a multiline `<textarea>` with JSON, a collapsed "Edit JSON" modal, or an inline key-value editor.
   - What's unclear: User expectation for JSON editing in a small node UI.
   - Recommendation: Start with a compact `<textarea rows="3">` with monospace font; add JSON parse error indicator. This is the simplest solution that fits the constraint.

3. **ParamType enum values: TypeScript vs Backend**
   - What we know: STATE.md says "ParamType uses list_of_strings/list_of_numbers/json_object" but the existing `cube.ts` still has `STRING_ARRAY`, `NUMBER_ARRAY`, `FLIGHT_IDS`, `JSON`. These may need reconciliation before handle color mapping works correctly.
   - Recommendation: Align `cube.ts` enum values with backend before implementing PARAM_COLORS map. This is a prerequisite task for Phase 4 Wave 0.

---

## Sources

### Primary (HIGH confidence)
- `https://reactflow.dev/learn/advanced-use/typescript` — Node typing, NodeProps, AppNode union pattern
- `https://reactflow.dev/learn/advanced-use/state-management` — Zustand + React Flow integration, applyNodeChanges/applyEdgeChanges
- `https://reactflow.dev/learn/customization/handles` — Handle IDs, per-handle isValidConnection, multiple handles
- `https://reactflow.dev/learn/customization/custom-nodes` — Custom node component pattern, nodrag class
- `https://reactflow.dev/learn/customization/theming` — colorMode, CSS variables, dark mode
- `https://reactflow.dev/examples/interaction/drag-and-drop` — onDrop, onDragOver, screenToFlowPosition
- `https://reactflow.dev/learn/troubleshooting/migrate-to-v12` — Breaking changes: package rename, measured dimensions, API renames
- `https://reactflow.dev/api-reference/components/background` — Background variants, gap, size, color
- `https://reactflow.dev/api-reference/hooks/use-react-flow` — screenToFlowPosition, setNodes, setEdges
- `https://reactflow.dev/api-reference/types/is-valid-connection` — IsValidConnection type, Connection object
- `https://www.joshwcomeau.com/css/backdrop-filter/` — Glassmorphism CSS pattern, blur extension technique

### Secondary (MEDIUM confidence)
- `https://github.com/xyflow/xyflow/discussions/3861` — Confirmed: useReactFlow cannot be used in Zustand store; recommended pattern is component-level handler
- Zustand v5 `create<T>()()` double-parentheses pattern — verified across multiple sources (npm docs, community guides)
- sonner zero-dependency dark-theme toast — verified via npm page and shadcn/ui adoption

### Tertiary (LOW confidence)
- `react-tag-input-component` — Chosen based on npm search results; needs validation during implementation that it's compact enough for node UI
- `ParamType` enum reconciliation (STRING_ARRAY vs list_of_strings) — inferred from STATE.md decision log; must be verified against live backend

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core libraries installed; versions confirmed from package.json
- Architecture: HIGH — React Flow + Zustand integration verified from official docs
- Pitfalls: HIGH — nodeTypes warning, v12 measured dimensions, and useReactFlow constraints verified from official migration docs
- Glassmorphism CSS: HIGH — standard CSS pattern, well-documented
- Complex param editors: MEDIUM — recommendation (textarea) is pragmatic but untested in this specific node size constraint

**Research date:** 2026-03-03
**Valid until:** 2026-06-01 (stable libraries; React Flow v12 and Zustand v5 are mature releases)
