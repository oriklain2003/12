# Phase 6: Results Display — Tables, Map, Bidirectional Interaction - Research

**Researched:** 2026-03-04
**Domain:** React table rendering, Leaflet/react-leaflet v5 maps, CSS resizable split pane, bidirectional selection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Results container:** Bottom drawer — slides up from the bottom of the canvas, takes up 1/3 of the canvas height
- **Drawer trigger:** Clicking a cube node opens/switches the drawer to show that cube's results
- **Drawer replaces modal:** The drawer is the detailed view; compact ResultsPanel on the node stays as-is
- **Table-map layout:** Side by side within the drawer — table on the left, map on the right
- **Map visibility:** Only appears when geo data (lat/lon pairs) is detected; otherwise table takes full width
- **Resizable split:** User can resize the split ratio by dragging a divider between table and map
- **Geo shape rendering:** Render actual shapes (point → CircleMarker, polygon → polygon layer), not generic pin markers
- **Marker click:** Scrolls to the corresponding row in the table
- **CartoDB dark tiles:** Required as map tile source
- **Selected row style:** Colored border (not filled background), clean and minimal
- **Table row click (with geo data):** Map flies to that location
- **Clicking already-selected row with geo data:** Re-focuses the map
- **Scroll-to-row behavior:** Scroll directly, no elaborate animation
- **Truncation warning:** Display when results exceed 100 rows (per BACK-11)

### Claude's Discretion
- Exact drawer slide animation and handle/grip styling
- Scroll speed for scroll-to-row
- FlyTo zoom level and animation duration on the map
- Geo column detection heuristic (column name patterns for lat/lon)
- Table column header sort indicator styling
- Divider/resize handle appearance between table and map
- Whether drawer has a close button, drag-to-resize height, or fixed 1/3 height
- Default split ratio when both table and map are visible
- Marker/shape styling (colors, opacity, stroke)
- How the drawer transitions when switching between cubes

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RSLT-01 | Results table auto-detects columns from JSON array data, renders as scrollable table with sortable column headers | Object.keys() on first row for column auto-detection; useState for sort state; CSS overflow-y: auto for scroll |
| RSLT-02 | Leaflet map panel with CartoDB dark tiles renders markers for result rows that contain lat/lon coordinate pairs | react-leaflet v5 MapContainer + TileLayer; GeoJSON component with pointToLayer for CircleMarker; heuristic column detection |
| RSLT-03 | Bidirectional interaction — clicking map marker highlights/scrolls to table row; clicking table row flies map to location | useRef array on tr elements for scrollIntoView; MapFlyTo child component using useMap() hook; shared selectedRowIndex state |
</phase_requirements>

---

## Summary

Phase 6 implements a bottom drawer that slides up over the canvas to display cube execution results in rich form. The drawer contains a sortable, scrollable table auto-generated from JSON result rows, and conditionally a Leaflet map when coordinate data is detected. The two panels are split horizontally with a draggable divider.

All required libraries are already installed: `leaflet` v1.9.4, `react-leaflet` v5.0.0, and `@types/leaflet` are in `package.json`. No new dependencies are needed. The table is hand-built (no TanStack Table or similar) using native HTML `<table>`, which is appropriate given the constraint of clean, minimal UI and no new library overhead.

The bidirectional interaction is the most architecturally interesting part. The pattern uses a shared `selectedRowIndex: number | null` state (local to the drawer, not Zustand), a `useRef` array of `<tr>` elements for imperative scroll, and a `MapFlyTo` child component nested inside `MapContainer` that reads selected state and calls `map.flyTo()` via the `useMap()` hook. This avoids the anti-pattern of storing a Leaflet map instance in React state.

**Primary recommendation:** Build the drawer as a single `ResultsDrawer.tsx` file that orchestrates `ResultsTable`, `ResultsMap`, and the resizable divider. Keep all selection state local to the drawer — do not put it in Zustand, since it is purely view state.

---

## Standard Stack

### Core (already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `leaflet` | 1.9.4 | Map engine — tiles, layers, markers, GeoJSON rendering | De facto standard for web maps |
| `react-leaflet` | 5.0.0 | React bindings for Leaflet | Official React wrapper; v5 is current stable |
| `@types/leaflet` | 1.9.21 | TypeScript types for Leaflet | Already installed; official type package |

### No Additional Libraries Needed

The following problems are solved without new packages:

| Problem | Solution |
|---------|---------|
| Sortable table | Native HTML `<table>` + `useState` sort state + `useMemo` sorted rows |
| Scrollable table | CSS `overflow-y: auto` on the tbody container |
| Resizable split | Mouse event handler + `useState` split ratio; pure CSS flex layout |
| Drawer animation | CSS `transform: translateY` transition |
| Geo column detection | Hand-written heuristic in `geoDetect.ts` |
| Row scrolling | `useRef` array + `element.scrollIntoView({ block: 'nearest' })` |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── components/
│   └── Results/
│       ├── ResultsDrawer.tsx      # Orchestrator: drawer shell, split layout, state
│       ├── ResultsDrawer.css      # Drawer animation, split pane, handle styles
│       ├── ResultsTable.tsx       # Sortable scrollable table component
│       ├── ResultsTable.css       # Table styles: headers, rows, selected border
│       ├── ResultsMap.tsx         # MapContainer + TileLayer + GeoJSON layer
│       └── ResultsMap.css         # Map container sizing
├── utils/
│   └── geoDetect.ts              # Column name heuristic for lat/lon pair detection
└── store/
    └── flowStore.ts              # Add: selectedResultNodeId: string | null
```

### Store Addition Required

`flowStore.ts` needs one new piece of state to allow `CubeNode` to trigger the drawer and `EditorPage` to mount it:

```typescript
// In FlowState interface — add:
selectedResultNodeId: string | null;
setSelectedResultNodeId: (nodeId: string | null) => void;

// In store implementation — add:
selectedResultNodeId: null,
setSelectedResultNodeId: (nodeId) => set({ selectedResultNodeId: nodeId }),
```

### Pattern 1: Drawer Shell Layout in EditorPage

The drawer mounts below the canvas in EditorPage. The `.app__body` flex column is extended to accommodate the drawer:

```tsx
// EditorPage.tsx — add ResultsDrawer below canvas body
<div className="app">
  <Toolbar />
  <div className="app__body">
    <CubeCatalog />
    <div className="app__canvas-area">
      <ReactFlowProvider>
        <FlowCanvas />
      </ReactFlowProvider>
      <ResultsDrawer />   {/* slides up from bottom of canvas area */}
    </div>
  </div>
  <Toaster position="bottom-right" theme="dark" />
</div>
```

CSS for the canvas area wrapper:

```css
/* App.css additions */
.app__canvas-area {
  flex: 1;
  position: relative;  /* drawer is absolute-positioned within this */
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
```

The drawer uses `position: absolute; bottom: 0; left: 0; right: 0` within `.app__canvas-area` and slides up/down with `transform: translateY(100%)` when closed.

### Pattern 2: Drawer Component Structure

```tsx
// ResultsDrawer.tsx
export function ResultsDrawer() {
  const selectedNodeId = useFlowStore((s) => s.selectedResultNodeId);
  const results = useFlowStore((s) => selectedNodeId ? s.results[selectedNodeId] : null);
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);
  const [splitRatio, setSplitRatio] = useState(0.55); // table gets 55% by default

  const geoInfo = useMemo(
    () => results ? detectGeoColumns(results.rows) : null,
    [results]
  );

  const isOpen = selectedNodeId !== null && results !== null;

  return (
    <div className={`results-drawer ${isOpen ? 'results-drawer--open' : ''}`}>
      <div className="results-drawer__handle" onClick={...} />
      {results && (
        <div className="results-drawer__content">
          <div className="results-drawer__table-pane" style={{ flex: `0 0 ${splitRatio * 100}%` }}>
            <ResultsTable
              rows={results.rows}
              truncated={results.truncated}
              geoInfo={geoInfo}
              selectedRowIndex={selectedRowIndex}
              onRowSelect={setSelectedRowIndex}
            />
          </div>
          {geoInfo && (
            <>
              <ResizeDivider onResize={setSplitRatio} />
              <div className="results-drawer__map-pane" style={{ flex: 1 }}>
                <ResultsMap
                  rows={results.rows}
                  geoInfo={geoInfo}
                  selectedRowIndex={selectedRowIndex}
                  onMarkerClick={setSelectedRowIndex}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

### Pattern 3: CubeNode Click Handler

Each CubeNode needs to open the drawer when clicked. React Flow nodes receive clicks via the node's `onClick` or the wrapping div. Since the node click currently does nothing for results, add a click on the header or a "View Results" button (only when results exist).

The cleanest approach: add an `onClick` to the `.cube-node__header` div that calls `setSelectedResultNodeId(id)`. This is consistent with the user decision "clicking a different cube switches the drawer."

```tsx
// CubeNode.tsx — in the header:
const setSelectedResultNodeId = useFlowStore((s) => s.setSelectedResultNodeId);
const hasResults = useFlowStore((s) => !!s.results[id]);

// On the header div:
<div
  className="cube-node__header"
  onClick={hasResults ? () => setSelectedResultNodeId(id) : undefined}
  style={{ cursor: hasResults ? 'pointer' : 'default' }}
>
```

### Pattern 4: Sortable Table

```tsx
// ResultsTable.tsx
export function ResultsTable({ rows, truncated, geoInfo, selectedRowIndex, onRowSelect }: Props) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  const columns = useMemo(() =>
    rows.length > 0 ? Object.keys(rows[0] as Record<string, unknown>) : [],
    [rows]
  );

  const sortedRows = useMemo(() => {
    if (!sortCol) return rows;
    return [...rows].sort((a, b) => {
      const av = (a as Record<string, unknown>)[sortCol];
      const bv = (b as Record<string, unknown>)[sortCol];
      const cmp = String(av ?? '').localeCompare(String(bv ?? ''), undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  // Scroll to selected row when selectedRowIndex changes
  useEffect(() => {
    if (selectedRowIndex !== null && rowRefs.current[selectedRowIndex]) {
      rowRefs.current[selectedRowIndex]!.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedRowIndex]);

  return (
    <div className="results-table__wrapper">
      {truncated && <div className="results-table__truncation-warning">Showing first 100 rows</div>}
      <div className="results-table__scroll">
        <table className="results-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} onClick={() => handleSort(col)} className="results-table__th">
                  {col}
                  {sortCol === col && <span>{sortDir === 'asc' ? ' ↑' : ' ↓'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, i) => (
              <tr
                key={i}
                ref={(el) => { rowRefs.current[i] = el; }}
                className={`results-table__row${selectedRowIndex === i ? ' results-table__row--selected' : ''}`}
                onClick={() => onRowSelect(i)}
              >
                {columns.map((col) => (
                  <td key={col}>{String((row as Record<string, unknown>)[col] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### Pattern 5: Map Component with useMap() for FlyTo

The key pattern for `flyTo` is a child component inside `MapContainer` that uses `useMap()`. This avoids storing the map instance in state.

```tsx
// ResultsMap.tsx
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon paths broken by Vite bundler
import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';
L.Icon.Default.prototype.options.iconUrl = markerIconUrl;
L.Icon.Default.prototype.options.iconRetinaUrl = markerIconRetinaUrl;
L.Icon.Default.prototype.options.shadowUrl = markerShadowUrl;
L.Icon.Default.imagePath = '';

// ─── Inner child component: imperative flyTo via useMap ───────────────────────
function MapController({ selectedRowIndex, rows, geoInfo }: ControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (selectedRowIndex === null) return;
    const row = rows[selectedRowIndex] as Record<string, unknown>;
    const lat = Number(row[geoInfo.latCol]);
    const lon = Number(row[geoInfo.lonCol]);
    if (isFinite(lat) && isFinite(lon)) {
      map.flyTo([lat, lon], 10, { animate: true, duration: 0.5 });
    }
  }, [selectedRowIndex, map, rows, geoInfo]);

  return null;
}

// ─── Main ResultsMap component ────────────────────────────────────────────────
export function ResultsMap({ rows, geoInfo, selectedRowIndex, onMarkerClick }: Props) {
  const geojson = useMemo(() => buildGeoJSON(rows, geoInfo), [rows, geoInfo]);

  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      className="results-map"
      zoomControl={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        subdomains={['a', 'b', 'c', 'd']}
        maxZoom={19}
      />
      <GeoJSON
        key={JSON.stringify(geojson)}  {/* force re-render when data changes */}
        data={geojson}
        pointToLayer={(_, latlng) => L.circleMarker(latlng, {
          radius: 6,
          fillColor: '#6366f1',
          color: '#818cf8',
          weight: 1.5,
          opacity: 1,
          fillOpacity: 0.7,
        })}
        onEachFeature={(feature, layer) => {
          layer.on('click', () => onMarkerClick(feature.properties.rowIndex));
        }}
        style={(feature) => feature?.geometry.type !== 'Point' ? {
          color: '#6366f1',
          fillColor: '#6366f1',
          weight: 1.5,
          fillOpacity: 0.3,
        } : {}}
      />
      <MapController
        selectedRowIndex={selectedRowIndex}
        rows={rows}
        geoInfo={geoInfo}
      />
    </MapContainer>
  );
}
```

### Pattern 6: GeoJSON Construction from Rows

Convert result rows to GeoJSON FeatureCollection. Detect geometry type: if the row has only a lat/lon pair (no geometry column), emit a Point Feature. If a `geometry` or `geojson` column exists containing a GeoJSON geometry object, use it directly.

```typescript
function buildGeoJSON(rows: unknown[], geoInfo: GeoInfo): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  rows.forEach((row, i) => {
    const r = row as Record<string, unknown>;
    const lat = Number(r[geoInfo.latCol]);
    const lon = Number(r[geoInfo.lonCol]);
    if (!isFinite(lat) || !isFinite(lon)) return;

    // Check for native geometry column
    const geomCol = geoInfo.geomCol;
    if (geomCol && r[geomCol] && typeof r[geomCol] === 'object') {
      features.push({
        type: 'Feature',
        geometry: r[geomCol] as GeoJSON.Geometry,
        properties: { rowIndex: i },
      });
    } else {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { rowIndex: i },
      });
    }
  });
  return { type: 'FeatureCollection', features };
}
```

### Pattern 7: Geo Column Detection (geoDetect.ts)

```typescript
// frontend/src/utils/geoDetect.ts

export interface GeoInfo {
  latCol: string;
  lonCol: string;
  geomCol?: string;  // optional: column containing GeoJSON geometry objects
}

const LAT_PATTERNS = /^(lat|latitude|lat_deg|y)$/i;
const LON_PATTERNS = /^(lon|lng|long|longitude|lon_deg|x)$/i;
const GEOM_PATTERNS = /^(geometry|geom|geojson|shape|the_geom)$/i;

export function detectGeoColumns(rows: unknown[]): GeoInfo | null {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const first = rows[0];
  if (typeof first !== 'object' || first === null) return null;

  const keys = Object.keys(first as Record<string, unknown>);

  const latCol = keys.find((k) => LAT_PATTERNS.test(k));
  const lonCol = keys.find((k) => LON_PATTERNS.test(k));

  if (!latCol || !lonCol) return null;

  // Validate that the columns actually contain numeric values
  const sample = first as Record<string, unknown>;
  if (!isFinite(Number(sample[latCol])) || !isFinite(Number(sample[lonCol]))) return null;

  const geomCol = keys.find((k) => GEOM_PATTERNS.test(k));

  return { latCol, lonCol, geomCol };
}
```

### Pattern 8: Resizable Split Divider

No library needed. Use a pointer-event-based drag handler on a thin divider element:

```tsx
// Inside ResultsDrawer.tsx
function ResizeDivider({ containerRef, onSplitChange }: DividerProps) {
  const isDragging = useRef(false);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    isDragging.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    onSplitChange(Math.min(0.85, Math.max(0.15, ratio)));
  }, [containerRef, onSplitChange]);

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    isDragging.current = false;
    e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  return (
    <div
      className="results-drawer__divider"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    />
  );
}
```

### Anti-Patterns to Avoid

- **Storing Leaflet map instance in useState:** Do not do `const [map, setMap] = useState<L.Map>()`. It causes stale closures and re-render issues. Use the `useMap()` hook inside a child component instead.
- **Putting `selectedRowIndex` in Zustand:** This is ephemeral view state that does not need to persist across renders or be shared beyond the drawer. Keep it in local `useState`.
- **Using `key` prop on MapContainer to re-mount the map:** This destroys and re-creates the map on every data switch, causing a flash. Only re-key the `GeoJSON` layer, not the `MapContainer`.
- **Calling `map.flyTo()` directly in a component that renders MapContainer:** `flyTo` must be called from WITHIN a MapContainer descendant via `useMap()`. A sibling or parent cannot call it directly.
- **Forgetting Leaflet CSS import:** `import 'leaflet/dist/leaflet.css'` must be imported once (in `ResultsMap.tsx`). Without it, the map renders without controls and tiles may be misaligned.
- **Forgetting the Vite icon path fix:** Default Leaflet marker icons break in Vite because Vite transforms CSS asset URLs. Fix with explicit imports of marker PNG assets (see Code Examples section).
- **Mutable `<GeoJSON>` component without `key` change:** react-leaflet's `GeoJSON` component does not re-render when `data` prop changes. Provide a `key` based on a hash or `JSON.stringify` of the data to force re-mounting the layer.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tile rendering | Custom tile system | Leaflet `TileLayer` | Handles zoom, tile loading, retina, attribution |
| GeoJSON polygon rendering | Custom SVG polygons | Leaflet `GeoJSON` component | Handles all geometry types, projection, hit testing |
| Circle markers for points | Custom DOM elements | `L.circleMarker()` via `pointToLayer` | Leaflet handles coordinate-to-pixel projection |

**Key insight:** The only custom code needed is the geo column detection heuristic and the table sort logic — everything else delegates to Leaflet's battle-tested implementation.

---

## Common Pitfalls

### Pitfall 1: Leaflet Default Marker Icon Broken in Vite
**What goes wrong:** Marker icons display as broken image (404 on PNG files) when running under Vite because Vite rewrites CSS asset URLs during bundling, confusing Leaflet's internal icon path resolver.
**Why it happens:** Leaflet's `L.Icon.Default` uses `_getIconUrl` which derives paths from its CSS at runtime. Vite transforms those paths in a way Leaflet doesn't expect.
**How to avoid:** Import marker PNG assets explicitly at the top of `ResultsMap.tsx` and set them on `L.Icon.Default.prototype.options` before any map renders. Set `L.Icon.Default.imagePath = ''` to disable the auto-detection entirely.
**Warning signs:** Marker appears as broken image square in dev or production build.

### Pitfall 2: GeoJSON Layer Not Updating When Data Changes
**What goes wrong:** Switching to a different cube's results shows stale map markers from the previous cube.
**Why it happens:** react-leaflet's `GeoJSON` component receives `data` as an immutable prop — it does not diff or re-render when `data` changes (unlike React components).
**How to avoid:** Set `key={JSON.stringify(geoData)}` or `key={nodeId}` on the `<GeoJSON>` component so React unmounts and remounts it when data changes.
**Warning signs:** Map shows markers from previous cube after switching.

### Pitfall 3: MapContainer Unmounting/Remounting on Cube Switch
**What goes wrong:** When switching between cubes, if `key` is placed on `MapContainer`, the map is destroyed and rebuilt, causing a visible flash and resetting zoom/pan.
**Why it happens:** Changing `key` on any React element forces a full unmount/remount.
**How to avoid:** Only put `key` on the `<GeoJSON>` layer inside the container, not on `<MapContainer>`. The container stays mounted while only the data layer refreshes.

### Pitfall 4: `useMap()` Called Outside MapContainer
**What goes wrong:** Calling `useMap()` in `ResultsDrawer` (outside `MapContainer`) throws a context error.
**Why it happens:** `useMap()` requires being called inside a descendant of `MapContainer`.
**How to avoid:** Create a dedicated `MapController` child component that is rendered inside `MapContainer`. Pass needed state down as props.

### Pitfall 5: Drawer Open/Close During Execution
**What goes wrong:** A cube's results are cleared and re-set during execution, potentially causing a flash or stale display.
**Why it happens:** `clearResults()` is called in `startExecution`, which sets `results = {}`, and the drawer reads from `results`.
**How to avoid:** The drawer should only show results when `results[selectedNodeId]` exists. The component already guards: `results && (...)`. When results are cleared, the drawer either shows empty state or closes gracefully.

### Pitfall 6: Sort State Stale After Data Switch
**What goes wrong:** Switching to a different cube's results while sort is active shows incorrect sorted order (old sort key that does not exist in new data).
**Why it happens:** `sortCol` state persists across cube switches.
**How to avoid:** In `ResultsTable`, use a `useEffect` that resets `setSortCol(null)` and `setSortDir('asc')` when the `rows` prop reference changes (via `useEffect([rows])`).

### Pitfall 7: Leaflet CSS Not Imported
**What goes wrong:** Map tiles render with offset or controls don't appear.
**Why it happens:** Leaflet's CSS is required for correct tile layering and control positioning.
**How to avoid:** Import `'leaflet/dist/leaflet.css'` in `ResultsMap.tsx`. This only needs to happen once in the render tree.

---

## Code Examples

### CartoDB Dark Tiles TileLayer

```tsx
// Source: CartoDB basemap-styles docs + leaflet-providers
<TileLayer
  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  subdomains={['a', 'b', 'c', 'd']}
  maxZoom={19}
/>
```

### Fix Leaflet Marker Icons in Vite

```typescript
// Source: https://willschenk.com/labnotes/2024/leaflet_markers_with_vite_build/
import L from 'leaflet';
import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.prototype.options.iconUrl = markerIconUrl;
L.Icon.Default.prototype.options.iconRetinaUrl = markerIconRetinaUrl;
L.Icon.Default.prototype.options.shadowUrl = markerShadowUrl;
L.Icon.Default.imagePath = '';
```

### useMap() for Imperative FlyTo

```tsx
// Source: https://react-leaflet.js.org/docs/api-map/ — useMap hook pattern
import { useMap } from 'react-leaflet';
import { useEffect } from 'react';

function MapController({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) {
      map.flyTo(target, 10, { animate: true, duration: 0.5 });
    }
  }, [target, map]);
  return null;
}
```

### GeoJSON eventHandlers (react-leaflet v5 syntax)

```tsx
// Source: https://react-leaflet.js.org/docs/api-components/ — Evented behavior
<GeoJSON
  data={geojsonData}
  onEachFeature={(feature, layer) => {
    layer.on('click', () => onMarkerClick(feature.properties.rowIndex));
  }}
  pointToLayer={(feature, latlng) =>
    L.circleMarker(latlng, { radius: 6, fillColor: '#6366f1', color: '#818cf8', weight: 1.5, fillOpacity: 0.7 })
  }
/>
```

### Drawer CSS (slide-up animation)

```css
/* ResultsDrawer.css */
.results-drawer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 33.33%;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border-hover);
  transform: translateY(100%);
  transition: transform var(--duration-normal) var(--ease-out);
  z-index: 20;
}

.results-drawer--open {
  transform: translateY(0);
}

.results-drawer__content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.results-drawer__divider {
  width: 5px;
  background: var(--color-border);
  cursor: col-resize;
  flex-shrink: 0;
  transition: background var(--duration-fast);
}

.results-drawer__divider:hover {
  background: var(--color-accent);
}
```

### Selected Row CSS (colored border, not fill)

```css
/* ResultsTable.css */
.results-table__row--selected td:first-child {
  border-left: 2px solid var(--color-accent);
}

.results-table__row {
  cursor: pointer;
  border-left: 2px solid transparent;  /* reserve space to avoid layout shift */
}

.results-table__row:hover {
  background: var(--color-surface-hover);
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-leaflet` v3 `<Map>` component | v5 `<MapContainer>` (immutable props) | v4+ | Props are set once; dynamic behavior requires hooks or child components |
| `map.ref` for imperative access | `useMap()` hook in child component | v4+ | Cannot use ref on MapContainer function component directly |
| `eventHandlers` prop object | `onEachFeature` + `layer.on()` for GeoJSON clicks | N/A | GeoJSON click must use native Leaflet `layer.on()` — react-leaflet `eventHandlers` applies to the layer group, not individual features |

**Deprecated/outdated:**
- `<Map>` component: Replaced by `<MapContainer>` in react-leaflet v3+. Do NOT use.
- `mapRef.current.leafletElement`: No longer available. Use `useMap()` hook instead.
- Storing `map` instance in `useState`: Causes infinite re-render loops due to Leaflet mutating the map object.

---

## Open Questions

1. **Geo data in Tracer 42 flight data format**
   - What we know: Flight data includes lat/lon fields (standard for flight tracking — takeoff/landing coordinates, waypoints)
   - What's unclear: Exact column names — could be `lat`/`lon`, `latitude`/`longitude`, or domain-specific names like `origin_lat`/`origin_lon`
   - Recommendation: The geo detection heuristic should be broader; also match `*_lat` and `*_lon` suffix patterns. Use `/(^|_)(lat|latitude)$/i` and `/(^|_)(lon|lng|longitude)$/i`.

2. **Polygon/shape data presence**
   - What we know: The user requested rendering actual shapes if the data has polygon geometry
   - What's unclear: Whether any current cube outputs polygon GeoJSON (Phase 7 DATA cubes are not yet implemented)
   - Recommendation: Implement the full GeoJSON path (point + polygon support) regardless. It costs nothing extra and will be needed when Phase 7 cubes arrive.

3. **Map initial bounds fitting**
   - What we know: `flyTo` is used for row-selected navigation; initial view is global `[20, 0], zoom 2`
   - What's unclear: Should the map auto-fit to all markers on initial render?
   - Recommendation: Yes — use `map.fitBounds(geojsonLayer.getBounds())` in an effect after GeoJSON loads. Implement via a `MapBoundsController` child component. This is a significant UX improvement at low cost.

---

## Sources

### Primary (HIGH confidence)
- react-leaflet official docs (https://react-leaflet.js.org/docs/api-map/) — `useMap` hook, `MapContainer` props
- react-leaflet official docs (https://react-leaflet.js.org/docs/api-components/) — component list, `GeoJSON`, `TileLayer`, `Marker`, eventHandlers prop
- Leaflet official docs (https://leafletjs.com/examples/geojson/) — `pointToLayer`, `onEachFeature`, `style`, GeoJSON rendering patterns
- Project `package.json` — confirmed versions: leaflet 1.9.4, react-leaflet 5.0.0, @types/leaflet 1.9.21

### Secondary (MEDIUM confidence)
- CartoDB basemap styles (https://github.com/CartoDB/basemap-styles) — dark_all tile URL pattern
- Will Schenk 2024 lab note (https://willschenk.com/labnotes/2024/leaflet_markers_with_vite_build/) — Vite marker icon fix; verified against multiple GitHub issues

### Tertiary (LOW confidence)
- Geo column name heuristics — derived from common naming conventions observed in geolib, pandas, and geospatial tooling; not from a single authoritative source

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — libraries confirmed in package.json, versions pinned
- Architecture patterns: HIGH — based on official react-leaflet docs + existing codebase patterns
- Table implementation: HIGH — native HTML table is simple and well-understood; no library ambiguity
- Pitfalls: HIGH — Leaflet/Vite icon issue is a well-documented, widely-reported problem with known fix
- Geo column heuristics: MEDIUM — naming conventions are standard in the geospatial community but domain-specific names for flight data are unknown

**Research date:** 2026-03-04
**Valid until:** 2026-09-04 (react-leaflet is stable; CartoDB tile URLs are long-lived)
