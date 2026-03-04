# Phase 6: Results Display — Tables, Map, Bidirectional Interaction - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Rich results viewing for cube outputs. Users click a cube node to see its full results in a bottom drawer containing a sortable table. When data contains geo coordinates, a Leaflet map renders alongside the table with bidirectional click interaction. Does NOT include new cube types, execution changes, or dashboard modifications.

Requirements: RSLT-01, RSLT-02, RSLT-03.

</domain>

<decisions>
## Implementation Decisions

### Results container
- Bottom drawer — slides up from the bottom of the canvas
- Takes up 1/3 of the canvas height
- Triggered by clicking on a cube node — shows that cube's results
- Clicking a different cube switches the drawer to show that cube's results (no need to close/reopen)
- Drawer replaces the compact ResultsPanel preview as the detailed view (ResultsPanel on the node stays as-is for quick glance)

### Table-map layout
- Side by side within the drawer — table on one side, map on the other
- Map only appears when geo data (lat/lon pairs) is detected in the results
- User can resize the split ratio by dragging a divider between table and map
- When no geo data exists, table takes the full drawer width

### Map markers & geo rendering
- Geo objects should render as their actual shape on the map (not generic pin markers) — if data represents a point, show a point; if it has a shape/polygon, render that shape
- Clicking a marker/shape on the map scrolls to the corresponding row in the table
- CartoDB dark tiles (already specified in requirements)

### Selection & interaction feedback
- Selected/highlighted table row: colored border (not filled background or fancy effect) — clean and minimal
- Clicking a table row with geo data: map focuses/flies to that location
- Clicking an already-selected row: nothing happens unless it has geo data, then re-focus the map to it
- Scroll-to-row behavior: just scroll there directly, no elaborate animation
- Truncation warning displayed when results exceed 100 rows (per BACK-11)

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

</decisions>

<specifics>
## Specific Ideas

- Keep it clean and minimal — no unnecessary animations or flashy effects
- The drawer should feel like a natural extension of the canvas, not a separate modal or overlay
- Geo shape rendering on map rather than generic pins — respect the data's actual geometry
- Resizable split gives users control without prescribing a fixed layout

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ResultsPanel.tsx`: Compact preview on CubeNode — reads `results[nodeId]` from Zustand store. Stays as-is; drawer is the detailed view
- `flowStore.ts`: Results stored as `Record<string, { rows: unknown[]; truncated: boolean }>` — drawer reads from this same store
- `leaflet` v1.9.4, `react-leaflet` v5.0.0, `@types/leaflet` already in package.json — no new map dependencies needed
- `theme.css`: Full dark theme CSS variables (backgrounds, borders, text, accents, shadows, radii)
- `glass.css`: Liquid glass utility classes — can be applied to the drawer surface
- `CubeNode.tsx`: Node click handler needed to trigger drawer — currently no onClick for results viewing

### Established Patterns
- Dark theme via CSS custom properties
- Zustand selectors for component-level state reads
- Glass effect via `glass--node` class pattern
- Category color accents on nodes (could inform which cube's results are shown)

### Integration Points
- `CubeNode.tsx` or `ResultsPanel.tsx`: needs click handler to open/switch drawer with node's results
- `FlowCanvas.tsx` or `EditorPage.tsx`: drawer component mounts here, below the canvas
- `flowStore.ts`: may need `selectedNodeForResults: string | null` state to track which cube's results are displayed
- New files per ROADMAP: `ResultsTable.tsx`, `ResultsMap.tsx`, `ResultsDrawer.tsx`, `geoDetect.ts`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-results-display-tables-map-bidirectional-interaction*
*Context gathered: 2026-03-04*
