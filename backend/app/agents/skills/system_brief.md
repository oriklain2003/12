# Tracer 42 — Visual Dataflow Workflow Builder for Flight Analysis

## What is Tracer 42?

Tracer 42 is a visual analysis platform for flight data. Analysts build analysis pipelines by dragging "cubes" (processing nodes) onto a canvas, configuring parameters, connecting outputs to inputs, and executing the pipeline against a PostgreSQL database containing real-world flight tracking data. No coding required.

The database is **read-only**. Results per cube execution are capped at 100,000 rows. Users are flight analysts — not developers.

## Data Sources

Two primary ADS-B (Automatic Dependent Surveillance-Broadcast) transponder data feeds:

- **all_flights** — OpenSky Network: global ADS-B feed covering commercial and general aviation
- **alison_flights** — Alison system: specialized regional ADS-B data feed

Additional derived data sources:
- **get_anomalies** — Pre-computed anomaly records from signal health analysis
- **get_flight_course** — Reconstructed flight path data for a specific flight
- **get_learned_paths** — Historical baseline flight corridors for route deviation detection

## Cube Categories

Cubes are self-contained processing units. Each cube has typed input and output parameters. There are five categories:

1. **data_source** — Fetch raw flight data from the database (e.g., `all_flights`, `alison_flights`, `get_anomalies`)
2. **filter** — Narrow result sets based on criteria (e.g., `squawk_filter`, `registration_country_filter`, `area_spatial_filter`)
3. **analysis** — Detect patterns and anomalies (e.g., `signal_health_analyzer`, `geo_temporal_playback`)
4. **aggregation** — Summarize and group results (e.g., `count_by_field`)
5. **output** — Format and present results (e.g., `echo`)

## Available Cubes

### Data Source Cubes
- **all_flights** — Query OpenSky Network ADS-B data. Params: time range, ICAO24, callsign, bounds.
- **alison_flights** — Query Alison system ADS-B data. Params: time range, ICAO24, callsign.
- **get_anomalies** — Retrieve pre-computed anomaly records. Params: time range, anomaly type.
- **get_flight_course** — Reconstruct a flight path. Params: ICAO24, time range.
- **get_learned_paths** — Load historical baseline corridors. Params: route key.

### Filter Cubes
- **squawk_filter** — Filter by squawk codes (emergency 7700, hijack 7500, communication failure 7600, special codes).
- **registration_country_filter** — Filter by aircraft registration country using ICAO24 prefix.
- **area_spatial_filter** — Filter by geographic polygon. Restricts flight records to those within a defined boundary.

### Analysis Cubes
- **signal_health_analyzer** — Detect ADS-B signal integrity issues: missing data gaps, impossible speed/altitude jumps, position anomalies.
- **geo_temporal_playback** — Reconstruct and replay aircraft movement over time on a map.

### Utility / Aggregation / Output Cubes
- **echo** — Pass data through unchanged; useful for debugging pipeline segments.
- **add_numbers** — Sum two numeric values (primarily for testing).
- **count_by_field** — Count records grouped by a specific field.

## Core Concepts

### Connections
Connections are parameter-level — users wire a specific output parameter of one cube to a specific input parameter of another. Type mismatches show a warning but are allowed. The special "full result" output bundles all output params as a JSON object and can be wired to any input marked `accepts_full_result: true`.

### Execution
Workflow execution uses topological sort to determine processing order. Manual input values are overridden when a connection provides a value. Results are capped at 100,000 rows per cube to prevent runaway queries.

### Workflow Graph
A workflow graph is a set of nodes (cubes with configurations) and edges (parameter-level connections). Nodes have a `cube_type` (which cube to instantiate) and a `values` dict (manually configured input parameters). Edges specify `source_cube`, `source_param`, `target_cube`, `target_param`.
