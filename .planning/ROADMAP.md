# Roadmap: Project 12 — Visual Dataflow Workflow Builder

## Milestones

- ✅ **v1.0 Visual Dataflow Workflow Builder** — Phases 1-10 (shipped 2026-03-06)
- 🔲 **v2.0 Advanced Flight Analysis Cubes** — Phases 11-14

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

### v2.0 Advanced Flight Analysis Cubes (Phases 11-14)

### Phase 11: Simple Filters — Squawk and Registration Country Cubes

**Goal:** Implement `alison_flights` data source, `squawk_filter`, and `registration_country_filter` cubes — the Alison provider pipeline foundation plus two filter cubes with dual-provider squawk support and ICAO24 country resolution.
**Cubes:** `alison_flights`, `squawk_filter`, `registration_country_filter`
**Depends on:** v1.0 (cube framework)
**Plans:** 3/3 plans complete

Plans:
- [ ] 11-01-PLAN.md — Alison data source cube + ICAO24 lookup module
- [ ] 11-02-PLAN.md — Squawk filter cube (dual-provider, code-change detection)
- [ ] 11-03-PLAN.md — Registration country filter cube + integration verification

### Phase 12: Area Spatial Filter with Geo Data Research

**Goal:** Implement `area_spatial_filter` cube with dual-provider polygon filtering, movement classification (landing/takeoff/cruise), and build geo data loader modules (country boundaries, FIR, land/water) for future spatial modes.
**Cubes:** `area_spatial_filter`
**Depends on:** Phase 11
**Plans:** 2/2 plans executed

Plans:
- [x] 12-01-PLAN.md — AreaSpatialFilterCube with dual-provider support and movement classification
- [x] 12-02-PLAN.md — Geo data loaders (country boundaries, FIR, land/water polygons)

### Phase 13: Flight Plans Source and Compliance Analyzer

**Goal:** Implement `flight_plans_source` (FlightAware AeroAPI v4) and `flight_plan_compliance_analyzer` cubes.
**Cubes:** `flight_plans_source`, `flight_plan_compliance_analyzer`
**Depends on:** Phase 11
**Plans:** 0 plans

**flight_plans_source:** Query FlightAware AeroAPI v4 for filed flight plans by airport. Add `FLIGHTAWARE_API_KEY` to config.
**flight_plan_compliance_analyzer:** Match ADS-B flights to filed plans, detect unfiled flights, urgent filings, route deviations.

Plans:
- [ ] TBD (run /gsd:plan-phase 13 to break down)

### Phase 14: Signal Health Analyzer

**Goal:** Implement `signal_health_analyzer` ANALYSIS cube with real detection logic ported from `scripts/` — rule-based integrity/shutdown detection + Kalman filter anomaly detection, Alison provider only, read-only.
**Cubes:** `signal_health_analyzer`
**Depends on:** Phase 11
**Plans:** 3 plans

Plans:
- [ ] 14-01-PLAN.md — Rule-based detection module (async port) + numpy/scipy dependencies
- [ ] 14-02-PLAN.md — Kalman detection module (async port)
- [ ] 14-03-PLAN.md — SignalHealthAnalyzerCube orchestrating both detection layers

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
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
| 11. Squawk & Reg Country | 3/3 | Complete   | 2026-03-06 | — |
| 12. Area Spatial Filter | v2.0 | 2/2 | Complete | 2026-03-08 |
| 13. Flight Plans & Compliance | v2.0 | 0/0 | Pending | — |
| 14. Signal Health Analyzer | v2.0 | 0/3 | Planned | — |

---
*Roadmap created: 2026-03-03*
*v1.0 shipped: 2026-03-06*
*v2.0 roadmap added: 2026-03-06*
