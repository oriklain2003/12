---
phase: 06-results-display-tables-map-bidirectional-interaction
plan: 02
requirements_completed: [RSLT-02, RSLT-03]
subsystem: frontend/results
tags: [leaflet, map, drawer, bidirectional, react-leaflet, geojson]
dependency_graph:
  requires:
    - 06-01 (geoDetect utility, ResultsTable, store extensions)
  provides:
    - ResultsMap component with CartoDB dark tiles and circle markers
    - ResultsDrawer orchestrator with resizable table+map split
    - CubeNode header click -> drawer open wiring
    - EditorPage canvas-area wrapper for drawer positioning
  affects:
    - frontend/src/pages/EditorPage.tsx
    - frontend/src/components/CubeNode/CubeNode.tsx
    - frontend/src/App.css
tech_stack:
  added:
    - react-leaflet v5 (MapContainer, TileLayer, GeoJSON, useMap)
    - leaflet v1.9 (L.circleMarker, L.latLngBounds, L.Icon.Default fix)
  patterns:
    - MapController/MapBoundsController inner components for useMap() hook access
    - GeoJSON key={JSON.stringify} for forced re-mount on data change
    - Pointer capture API for drag-resize divider
    - Local (useState) ephemeral view state, not Zustand
key_files:
  created:
    - frontend/src/components/Results/ResultsMap.tsx
    - frontend/src/components/Results/ResultsMap.css
    - frontend/src/components/Results/ResultsDrawer.tsx
    - frontend/src/components/Results/ResultsDrawer.css
    - frontend/src/vite-env.d.ts
  modified:
    - frontend/src/pages/EditorPage.tsx
    - frontend/src/App.css
    - frontend/src/components/CubeNode/CubeNode.tsx
decisions:
  - GeoJSON layer uses key={JSON.stringify(geojson)} to force re-mount on cube switch, not MapContainer key
  - ResizeDivider uses pointer capture for clean drag outside element bounds
  - selectedRowIndex is local state (not Zustand) — ephemeral view state
  - L.Icon.Default icon fix applied by mutating prototype options (Vite compatibility)
  - MapBoundsController auto-fits bounds once per data load via rows+geoInfo dependency
metrics:
  duration: "2 min"
  completed_date: "2026-03-04"
  tasks_completed: 2
  files_created: 5
  files_modified: 3
---

# Phase 06 Plan 02: ResultsDrawer + ResultsMap + Editor Wiring Summary

Leaflet map with CartoDB dark tiles, GeoJSON circle markers, and ResizeDivider-split drawer wired into the editor via CubeNode header click.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ResultsMap component | 72a4371 | ResultsMap.tsx, ResultsMap.css, vite-env.d.ts |
| 2 | Create ResultsDrawer and wire into EditorPage + CubeNode | d3b8c71 | ResultsDrawer.tsx, ResultsDrawer.css, EditorPage.tsx, App.css, CubeNode.tsx |

## What Was Built

### ResultsMap (Task 1)

A Leaflet map component rendering geo data from cube results:

- **CartoDB dark tiles** via `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png` — consistent dark theme
- **Circle markers** (`L.circleMarker`) with indigo fill, not default pin icons — per user decision
- **GeoJSON layer** keyed by JSON.stringify to force re-mount on cube switch (Pitfall 2 from research)
- **MapController** inner component: `useMap()` + `useEffect` on `selectedRowIndex` -> `map.flyTo([lat, lon], 10)`
- **MapBoundsController** inner component: auto-fits all valid points on data load via `map.fitBounds`
- **Vite icon fix**: `L.Icon.Default.prototype.options` overridden with explicit PNG imports
- `vite-env.d.ts` created with `declare module 'leaflet/dist/images/*.png'`

### ResultsDrawer (Task 2)

Orchestrator component managing table+map display:

- **Slides up** from canvas bottom, 33.33% height, `translateY(100%)` -> `translateY(0)` transition
- **Handle grip** (40px wide, 3px tall) at top — click to close
- **Header**: cube name + Close button
- **Table pane**: full width when no geo, `flex: 0 0 55%` when map is shown
- **ResizeDivider**: pointer capture API, clamped 15-85%, `col-resize` cursor, accent color on hover
- **Map pane**: `flex: 1`, only shown when `geoInfo` is non-null
- Local `selectedRowIndex` state — resets when cube selection changes
- Local `splitRatio` state (default 0.55) — ephemeral, not persisted

### Editor Wiring (Task 2 cont.)

- **EditorPage**: canvas wrapped in `<div className="app__canvas-area">` — positioning context for absolute drawer
- **App.css**: `.app__canvas-area { flex:1; position:relative; overflow:hidden; display:flex; flex-direction:column }`
- **CubeNode**: header gets `onClick` and `cursor:pointer` when `hasResults` is true — triggers `setSelectedResultNodeId(id)`

## Bidirectional Interaction Flow

```
Row click (ResultsTable.onRowSelect)
  -> setSelectedRowIndex(index)        [local state in ResultsDrawer]
  -> ResultsMap.selectedRowIndex prop
  -> MapController useEffect
  -> map.flyTo([lat, lon], 10)

Marker click (GeoJSON.onEachFeature layer.on('click'))
  -> onMarkerClick(feature.properties.rowIndex)
  -> setSelectedRowIndex(index)        [local state in ResultsDrawer]
  -> ResultsTable.selectedRowIndex prop
  -> rowRefs.current[index].scrollIntoView({ block: 'nearest' })
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `frontend/src/components/Results/ResultsMap.tsx` — created
- [x] `frontend/src/components/Results/ResultsMap.css` — created
- [x] `frontend/src/components/Results/ResultsDrawer.tsx` — created
- [x] `frontend/src/components/Results/ResultsDrawer.css` — created
- [x] `frontend/src/vite-env.d.ts` — created
- [x] `frontend/src/pages/EditorPage.tsx` — updated with ResultsDrawer and app__canvas-area
- [x] `frontend/src/App.css` — updated with .app__canvas-area class
- [x] `frontend/src/components/CubeNode/CubeNode.tsx` — updated with header click handler
- [x] Commit 72a4371 — Task 1
- [x] Commit d3b8c71 — Task 2
- [x] TypeScript compiles clean (`npx tsc --noEmit` exit 0)
