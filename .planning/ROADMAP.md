# Roadmap: Project 12 — Visual Dataflow Workflow Builder

## Milestones

- ✅ **v1.0 Visual Dataflow Workflow Builder** — Phases 1-10 (shipped 2026-03-06)
- ✅ **v2.0 Advanced Flight Analysis Cubes** — Phases 11-17 (shipped 2026-03-13, Phase 13 deferred)
- ✅ **v3.0 AI Workflow Agents** — Phases 18-22 (shipped 2026-03-27)
- 🚧 **v4.0 Flight Behavioral Analysis** — Phases 23-26 (in progress)

## Phases

<details>
<summary>✅ v1.0 Visual Dataflow Workflow Builder (Phases 1-10) — SHIPPED 2026-03-06</summary>

- [x] Phase 1: Types, Schemas & Project Scaffolding (2/2 plans) — completed 2026-03-03
- [x] Phase 2: Backend Core — Registry, DB, CRUD, Executor (2/2 plans) — completed 2026-03-03
- [x] Phase 3: Async Execution with SSE Progress (1/1 plans) — completed 2026-03-03
- [x] Phase 4: Frontend Canvas, Nodes, Sidebar & Dark Theme (3/3 plans) — completed 2026-03-04
- [x] Phase 5: Workflow Management & Execution Integration (3/3 plans) — completed 2026-03-04
- [x] Phase 6: Results Display — Tables, Map, Bidirectional Interaction (2/2 plans) — completed 2026-03-04
- [x] Phase 7: Real DB Cubes, End-to-End & Docker (3/3 plans) — completed 2026-03-04
- [x] Phase 8: Geo-Temporal Playback, Learned Paths & Flight Course Cubes (4/4 plans) — completed 2026-03-05
- [x] Phase 9: Filter Flights Cube — Gap Closure (1/1 plans) — completed 2026-03-05
- [x] Phase 10: Audit Remediation — Gap Closure (2/2 plans) — completed 2026-03-05

**Full details:** .planning/milestones/v1.0-ROADMAP.md

</details>

<details>
<summary>✅ v2.0 Advanced Flight Analysis Cubes (Phases 11-17) — SHIPPED 2026-03-13</summary>

- [x] Phase 11: Simple Filters — Squawk and Registration Country Cubes (3/3 plans) — completed 2026-03-06
- [x] Phase 12: Area Spatial Filter with Geo Data Research (2/2 plans) — completed 2026-03-08
- [ ] Phase 13: Flight Plans Source and Compliance Analyzer — **deferred** (FlightAware API dependency)
- [x] Phase 14: Signal Health Analyzer (3/3 plans) — completed 2026-03-08
- [x] Phase 15: Cube Tests (7/7 plans) — completed 2026-03-09
- [x] Phase 16: Signal Health Fixes (3/3 plans) — completed 2026-03-13
- [x] Phase 17: Squawk Optimization (1/1 plans) — completed 2026-03-13

**Note:** Phase 13 deferred — requires FlightAware AeroAPI v4 access. All other phases complete.

</details>

<details>
<summary>✅ v3.0 AI Workflow Agents (Phases 18-22) — SHIPPED 2026-03-27</summary>

- [x] Phase 18: Agent Infrastructure (4/4 plans) — completed 2026-03-24
- [x] Phase 19: Cube Expert + Validation Agent (3/3 plans) — completed 2026-03-24
- [x] Phase 20: Canvas Agent (4/4 plans) — completed 2026-03-25
- [x] Phase 21: Build Wizard Agent (3/3 plans) — completed 2026-03-27
- [x] Phase 22: Results Interpreter (2/2 plans) — completed 2026-03-27

**Full details:** .planning/milestones/v3.0-ROADMAP.md

</details>

### 🚧 v4.0 Flight Behavioral Analysis (In Progress)

**Milestone Goal:** Add behavioral analysis and anomaly detection cubes that compare individual flights against historical patterns, plus enhance existing cubes with duration filtering and flexible datetime/lookback parameters.

- [ ] **Phase 23: Shared Utility Foundation + Duration Filter** - Shared historical query utilities, epoch helpers, and FilterFlights duration params
- [ ] **Phase 24: No Recorded Takeoff Cube** - Detection cube establishing the output schema pattern for all behavioral cubes
- [ ] **Phase 25: Statistical Behavioral Analysis** - Unusual takeoff location and time detection using historical baselines
- [ ] **Phase 26: O/D Verification + Route Statistics** - Origin/destination verification and route frequency aggregation cubes

## Phase Details

### Phase 23: Shared Utility Foundation + Duration Filter
**Goal**: Shared infrastructure for all behavioral cubes is in place and FilterFlights has duration filtering
**Depends on**: Phase 22 (prior milestone complete)
**Requirements**: INFRA-01, INFRA-02, INFRA-04, ENHANCE-01, ENHANCE-02, ENHANCE-03
**Success Criteria** (what must be TRUE):
  1. User can filter flights by minimum and maximum flight duration (minutes) using FilterFlights cube
  2. Partial datetime input (only start or only end) raises a descriptive error visible in the cube output
  3. A datetime/lookback toggle parameter is available on cubes that query historical data, letting user switch between a fixed date range and a rolling lookback window
  4. All historical queries batch callsign lookups via asyncio.gather() — no per-flight DB round-trips
**Plans**: TBD

### Phase 24: No Recorded Takeoff Cube
**Goal**: Users can detect flights with no recorded takeoff using the new cube, establishing the behavioral output schema pattern
**Depends on**: Phase 23
**Requirements**: INFRA-03, DETECT-01, DETECT-05, DETECT-06
**Success Criteria** (what must be TRUE):
  1. User can place a No Recorded Takeoff cube on the canvas, connect AllFlights or FilterFlights output to it, and run — cube flags flights whose first track point is at or above the configurable altitude threshold (default 300 ft)
  2. Cube accepts a full_result input so it works drop-in after any upstream cube without explicit parameter wiring
  3. Each output row includes a numeric deviation_score (0.0–1.0) alongside the boolean flag
  4. Each output row includes a diagnostic field distinguishing "no anomalies found", "insufficient history", and "empty input" states
**Plans**: TBD

### Phase 25: Statistical Behavioral Analysis
**Goal**: Users can detect flights with unusual takeoff locations and unusual takeoff times relative to historical baselines
**Depends on**: Phase 24
**Requirements**: DETECT-02, DETECT-03
**Success Criteria** (what must be TRUE):
  1. User can detect unusual takeoff locations — cube compares each flight's departure coordinates against the historical centroid for that callsign/route and flags flights exceeding the configurable distance threshold (default 5 NM)
  2. User can detect unusual takeoff times — cube compares each flight's departure time against the historical circular mean using configurable stddev threshold (default 2.0)
  3. Both cubes output deviation_score and diagnostic fields consistent with the schema established in Phase 24
  4. Both cubes use the shared historical_query.py utilities from Phase 23 with batch asyncio.gather() fetch pattern
**Plans**: TBD

### Phase 26: O/D Verification + Route Statistics
**Goal**: Users can verify origin/destination against historical patterns and compute route frequency statistics
**Depends on**: Phase 25
**Requirements**: DETECT-04, DETECT-07, STATS-01, STATS-02, STATS-03
**Success Criteria** (what must be TRUE):
  1. User can verify a flight's origin and destination against historical patterns — cube flags flights whose O/D pair deviates from the callsign's most common historical route
  2. O/D Verification cube uses an extensible internal check registry so additional checks can be added in future without changing the cube interface
  3. User can compute average number of flights per route over a configurable time window — output includes total count, average, min, and max
  4. User can compute average flights per day-of-week for a given route — output is a 7-element distribution enabling pattern-of-life analysis
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Types & Schemas | v1.0 | 2/2 | Complete | 2026-03-03 |
| 2. Backend Core | v1.0 | 2/2 | Complete | 2026-03-03 |
| 3. SSE Execution | v1.0 | 1/1 | Complete | 2026-03-03 |
| 4. Frontend Canvas | v1.0 | 3/3 | Complete | 2026-03-04 |
| 5. Workflow Mgmt | v1.0 | 3/3 | Complete | 2026-03-04 |
| 6. Results Display | v1.0 | 2/2 | Complete | 2026-03-04 |
| 7. Real DB + Docker | v1.0 | 3/3 | Complete | 2026-03-04 |
| 8. Geo-Temporal | v1.0 | 4/4 | Complete | 2026-03-05 |
| 9. Filter Flights | v1.0 | 1/1 | Complete | 2026-03-05 |
| 10. Audit Remediation | v1.0 | 2/2 | Complete | 2026-03-05 |
| 11. Squawk & Reg Country | v2.0 | 3/3 | Complete | 2026-03-06 |
| 12. Area Spatial Filter | v2.0 | 2/2 | Complete | 2026-03-08 |
| 13. Flight Plans & Compliance | v2.0 | 0/0 | Deferred | — |
| 14. Signal Health Analyzer | v2.0 | 3/3 | Complete | 2026-03-08 |
| 15. Cube Tests | v2.0 | 7/7 | Complete | 2026-03-09 |
| 16. Signal Health Fixes | v2.0 | 3/3 | Complete | 2026-03-13 |
| 17. Squawk Optimization | v2.0 | 1/1 | Complete | 2026-03-13 |
| 18. Agent Infrastructure | v3.0 | 4/4 | Complete | 2026-03-24 |
| 19. Cube Expert + Validation | v3.0 | 3/3 | Complete | 2026-03-24 |
| 20. Canvas Agent | v3.0 | 4/4 | Complete | 2026-03-25 |
| 21. Build Wizard Agent | v3.0 | 3/3 | Complete | 2026-03-27 |
| 22. Results Interpreter | v3.0 | 2/2 | Complete | 2026-03-27 |
| 23. Shared Utility Foundation | v4.0 | 0/TBD | Not started | — |
| 24. No Recorded Takeoff | v4.0 | 0/TBD | Not started | — |
| 25. Statistical Behavioral Analysis | v4.0 | 0/TBD | Not started | — |
| 26. O/D Verification + Route Stats | v4.0 | 0/TBD | Not started | — |

---
*Roadmap created: 2026-03-03*
*v1.0 shipped: 2026-03-06*
*v2.0 shipped: 2026-03-13 (Phase 13 deferred)*
*v3.0 shipped: 2026-03-27*
*v4.0 roadmap added: 2026-03-29*
