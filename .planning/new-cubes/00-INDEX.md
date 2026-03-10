# New Cubes Planning Index

Total: 42 new cubes across 10 categories.

## Files

| # | File | Category | Cubes |
|---|------|----------|-------|
| 01 | [01-identity-and-ownership.md](01-identity-and-ownership.md) | Identity & Ownership Intelligence | 4 cubes (#1-4) |
| 02 | [02-behavioral-analysis.md](02-behavioral-analysis.md) | Behavioral Analysis (FR24-powered) | 5 cubes (#5-9) |
| 03 | [03-geopolitical-and-conflict.md](03-geopolitical-and-conflict.md) | Geopolitical & Conflict Intelligence | 4 cubes (#10-13) |
| 04 | [04-signal-and-electronic-warfare.md](04-signal-and-electronic-warfare.md) | Signal & Electronic Warfare | 2 cubes (#14-15) |
| 05 | [05-maritime-aviation-correlation.md](05-maritime-aviation-correlation.md) | Maritime-Aviation Correlation | 2 cubes (#16-17) |
| 06 | [06-weather-and-environment.md](06-weather-and-environment.md) | Weather & Environment | 2 cubes (#18-19) |
| 07 | [07-reference-and-enrichment.md](07-reference-and-enrichment.md) | Reference & Enrichment | 3 cubes (#20-22) |
| 08 | [08-advanced-analysis.md](08-advanced-analysis.md) | Advanced Analysis | 4 cubes (#23-26) |
| 09 | [09-fr24-data-sources.md](09-fr24-data-sources.md) | FlightRadar24 API Data Sources | 6 cubes (#27-32) |
| 10 | [10-middle-east-intelligence.md](10-middle-east-intelligence.md) | Middle East Intelligence | 10 cubes (#33-42) |

## Cube Summary

| # | Cube ID | Category | Primary Data Source | Cost |
|---|---------|----------|-------------------|------|
| 1 | `aircraft_enrichment` | Identity | hexdb.io + FAA Registry + local DB | Free |
| 2 | `sanctions_screener` | Identity | US CSL API + OpenSanctions | Free |
| 3 | `ownership_chain_tracker` | Identity | FAA Registry + FR24 | Free + Credits |
| 4 | `registration_country_risk` | Identity | CPI + FATF + local | Free |
| 5 | `pattern_of_life` | Behavioral | FR24 + local DB | Credits |
| 6 | `dark_flight_detector` | Behavioral | Local DB (coverage_grid) | Free |
| 7 | `holding_pattern_detector` | Behavioral | Local DB (tracks) | Free |
| 8 | `meeting_detector` | Behavioral | FR24 + local DB | Free + Credits |
| 9 | `route_deviation_analyzer` | Behavioral | Local DB (learned_tubes/paths/sids/stars) | Free |
| 10 | `conflict_zone_overlay` | Geopolitical | ACLED API | Free |
| 11 | `notam_checker` | Geopolitical | aviationweather.gov | Free |
| 12 | `airspace_closure_detector` | Geopolitical | Local DB (live schema) | Free |
| 13 | `arms_transfer_tracker` | Geopolitical | Local DB + SIPRI | Free |
| 14 | `jamming_zone_detector` | Signal/EW | Local DB (jamming_grid) | Free |
| 15 | `spoofing_cluster_analyzer` | Signal/EW | Local DB (anomaly_events + kalman_events) | Free |
| 16 | `maritime_flight_correlator` | Maritime | Local DB (marine + tracks) | Free |
| 17 | `vessel_tracker` | Maritime | Local DB (marine tables) | Free |
| 18 | `weather_enrichment` | Weather | aviationweather.gov | Free |
| 19 | `fire_detection_overlay` | Weather | NASA FIRMS | Free |
| 20 | `airport_enrichment` | Reference | OurAirports CSV | Free |
| 21 | `airspace_lookup` | Reference | OpenAIP + Eurocontrol | Free |
| 22 | `fr24_airport_activity` | Reference | FR24 + local DB | Free + Credits |
| 23 | `set_operations` | Advanced | None (pure logic) | Free |
| 24 | `network_graph_builder` | Advanced | Upstream data | Free |
| 25 | `temporal_heatmap` | Advanced | Local DB / upstream | Free |
| 26 | `proximity_detector` | Advanced | Local DB (tracks) | Free |
| 27 | `fr24_live_flights` | FR24 Source | FR24 API | Credits |
| 28 | `fr24_flight_history` | FR24 Source | FR24 API | Credits |
| 29 | `fr24_flight_summary` | FR24 Source | FR24 API | Credits |
| 30 | `fr24_flight_tracks` | FR24 Source | FR24 API | Credits |
| 31 | `fr24_airline_info` | FR24 Source | FR24 API | Credits |
| 32 | `fr24_airport_info` | FR24 Source | FR24 API | Credits |
| 33 | `iran_axis_monitor` | Middle East | Local DB | Free |
| 34 | `me_jamming_dashboard` | Middle East | Local DB (jamming_grid) | Free |
| 35 | `military_callsign_decoder` | Middle East | Local DB + static tables | Free |
| 36 | `border_crossing_analyzer` | Middle East | Local DB (live schema) | Free |
| 37 | `syria_iraq_airport_monitor` | Middle East | Local DB | Free |
| 38 | `red_sea_corridor_monitor` | Middle East | Local DB + marine tables | Free |
| 39 | `signal_loss_corridor_mapper` | Middle East | Local DB (live schema) | Free |
| 40 | `airspace_rerouting_detector` | Middle East | Local DB (learned_tubes) | Free |
| 41 | `gulf_sanctions_hub_tracker` | Middle East | Local DB | Free |
| 42 | `me_anomaly_enricher` | Middle East | Local DB (multiple tables) | Free |

## External Data Sources Used

| Source | Cost | Auth Required | Used By |
|--------|------|---------------|---------|
| hexdb.io API | Free | No | #1 |
| FAA N-Number Registry (CSV) | Free | No | #1, #3 |
| US Consolidated Screening List API | Free | API key | #2 |
| OpenSanctions API | Free (non-commercial) | No | #2 |
| Transparency International CPI | Free | No | #4 |
| FATF grey/black lists | Free | No | #4 |
| ACLED API | Free | API key + email | #10 |
| aviationweather.gov API | Free | No | #11, #18 |
| SIPRI Arms Transfers | Free | No | #13 |
| NASA FIRMS API | Free | MAP_KEY (email) | #19 |
| OurAirports CSVs | Free (public domain) | No | #7, #8, #20 |
| OpenAIP | Free (non-commercial) | No | #21 |
| Eurocontrol Atlas (GitHub) | Free | No | #21 |
| FR24 API (fr24sdk) | Paid (credits) | API token | #5, #8, #22, #27-32 |
| GPSJam.org | Free | No | #14 |

## Unused Local DB Tables Unlocked

| Table | Records | Unlocked By Cube |
|-------|---------|-----------------|
| `public.jamming_grid` | Growing | #14 jamming_zone_detector |
| `public.coverage_grid` | 7,769 | #6 dark_flight_detector |
| `public.anomaly_events` | 29,801 | #15 spoofing_cluster_analyzer |
| `public.kalman_events` | Growing | #15 spoofing_cluster_analyzer |
| `public.rule_based_events` | Growing | #15 spoofing_cluster_analyzer |
| `public.learned_sids` | 189 | #9 route_deviation_analyzer |
| `public.learned_stars` | 88 | #9 route_deviation_analyzer |
| `public.learned_tubes` | 3,145 | #9 route_deviation_analyzer |
| `marine.vessel_metadata` | 7,142 | #16, #17 |
| `marine.vessel_positions` | Growing | #16, #17 |
| `live.flight_metadata` | Growing | #12, #13, #22 |
| `live.normal_tracks` | Growing | #12 |
| `feedback.user_feedback` | 1,644 | (future cube) |

## Implementation Priority

### Tier 1 — Quick wins (use existing DB, no external APIs)
1. `set_operations` (#23) — pure logic, massive workflow value
2. `jamming_zone_detector` (#14) — jamming_grid data sitting unused
3. `vessel_tracker` (#17) — marine tables ready
4. `dark_flight_detector` (#6) — coverage_grid data sitting unused
5. `route_deviation_analyzer` (#9) — 3,145 learned tubes ready

### Tier 2 — Free external APIs
6. `sanctions_screener` (#2) — US CSL API is free
7. `aircraft_enrichment` (#1) — hexdb.io is free
8. `weather_enrichment` (#18) — aviationweather.gov is free
9. `airport_enrichment` (#20) — OurAirports is public domain
10. `conflict_zone_overlay` (#10) — ACLED is free

### Tier 3 — Analysis cubes (no external deps)
11. `holding_pattern_detector` (#7) — algorithmic, uses local tracks
12. `spoofing_cluster_analyzer` (#15) — anomaly_events + DBSCAN
13. `airspace_closure_detector` (#12) — live schema traffic analysis
14. `proximity_detector` (#26) — track comparison
15. `temporal_heatmap` (#25) — time-series aggregation

### Tier 4 — Middle East Intelligence (all free, local DB)
16. `iran_axis_monitor` (#33) — Tehran-Damascus-Beirut corridor, uses existing metadata
17. `me_jamming_dashboard` (#34) — named ME jamming zones, unlocks jamming_grid
18. `military_callsign_decoder` (#35) — classify HERC30, GAF901, POKER45 etc.
19. `border_crossing_analyzer` (#36) — leverages crossed_borders field
20. `signal_loss_corridor_mapper` (#39) — EL AL signal losses already in DB
21. `airspace_rerouting_detector` (#40) — uses 3,145 learned tubes as baseline
22. `syria_iraq_airport_monitor` (#37) — new operators at OSDI, OSLK, ORBI
23. `red_sea_corridor_monitor` (#38) — Houthi threat zone + marine data
24. `gulf_sanctions_hub_tracker` (#41) — Dubai/Sharjah transshipment detection
25. `me_anomaly_enricher` (#42) — context layer on existing anomaly output

### Tier 5 — FR24 API integration
26. FR24 data source cubes (#27-32) — requires fr24sdk setup
27. `pattern_of_life` (#5) — needs FR24 for deep history
28. `fr24_airport_activity` (#22) — airport monitoring
29. `meeting_detector` (#8) — co-location analysis
