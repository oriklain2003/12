# Category IV: Signal & Electronic Warfare Cubes

## 14. `jamming_zone_detector` — GPS Interference Mapping

**Purpose:** Surface active GPS jamming zones by combining your pre-computed jamming grid data with external interference reports. Produce heatmap-ready output for visualization on the map.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | No | Area of interest [[lat, lon], ...] (default: global) |
| `time_range_hours` | NUMBER | No | Recent hours to analyze (default: 24) |
| `min_jamming_pct` | NUMBER | No | Minimum jamming percentage to include cell (default: 5.0) |
| `min_degraded_reports` | NUMBER | No | Minimum degraded reports per cell (default: 3) |
| `include_notams` | BOOLEAN | No | Cross-reference GPS interference NOTAMs (default: true) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `zones` | JSON_OBJECT | Array of active jamming zone cells with stats |
| `heatmap_data` | JSON_OBJECT | GeoJSON FeatureCollection for heatmap rendering |
| `affected_aircraft_count` | NUMBER | Total unique aircraft affected |
| `hotspots` | JSON_OBJECT | Clustered high-jamming regions with center, radius, intensity |
| `gps_notams` | JSON_OBJECT | Matching GPS interference NOTAMs (if enabled) |

**Zone cell fields:** lat_cell, lon_cell, hour_start, total_reports, degraded_reports, jamming_pct, unique_aircraft, geometry (GeoJSON Polygon for the cell)

**Hotspot fields:** center_lat, center_lon, radius_km, avg_jamming_pct, peak_jamming_pct, total_affected_aircraft, first_seen, last_seen

### Logic
1. Query `public.jamming_grid` filtered by:
   - Time range (`hour_start` within last N hours)
   - Geographic area (lat_cell/lon_cell within polygon bounding box)
   - Minimum thresholds (jamming_pct, degraded_reports)
2. Cluster adjacent high-jamming cells into hotspot regions (DBSCAN or connected-component grouping)
3. For each hotspot: compute center, extent, intensity metrics
4. Convert grid cells to GeoJSON polygons for heatmap rendering
5. If `include_notams`: query aviationweather.gov for GPS interference NOTAMs in the same area
6. Cross-reference: jamming detected + matching NOTAM = confirmed; jamming without NOTAM = unreported

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `public.jamming_grid` (local DB) | PostgreSQL | Free | N/A |
| **aviationweather.gov** (NOTAMs) | REST API | Free | Reasonable use |
| **GPSJam.org** | Web/Data (crowd-sourced ADS-B NACp) | Free | Scraping only |

### Implementation Notes
- Your `jamming_grid` table is currently unused — this cube unlocks it
- Grid cells are 0.5° × 0.5° (lat/lon) with hourly granularity
- Heatmap GeoJSON output can be rendered with a new frontend widget (or via `geo_temporal_playback`)
- Widget hint: `"heatmap"` for a dedicated heatmap visualization
- Category: **ANALYSIS**

---

## 15. `spoofing_cluster_analyzer` — GPS Spoofing Campaign Detection

**Purpose:** Cluster GPS spoofing events in space and time to identify coordinated spoofing campaigns. Goes beyond individual event detection (already done by `signal_health_analyzer`) to find patterns across multiple aircraft.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `time_range_hours` | NUMBER | No | Lookback period (default: 72) |
| `polygon` | JSON_OBJECT | No | Area of interest (default: global) |
| `min_cluster_size` | NUMBER | No | Minimum events to form a cluster (default: 3) |
| `cluster_radius_km` | NUMBER | No | Maximum distance between events in a cluster (default: 50) |
| `cluster_time_window_hours` | NUMBER | No | Maximum time span within a cluster (default: 12) |
| `event_types` | LIST_OF_STRINGS | No | `["gps_spoofing", "gps_jamming", "probable_jamming"]` (default: all) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `clusters` | JSON_OBJECT | Array of detected spoofing/jamming campaigns |
| `isolated_events` | JSON_OBJECT | Events not belonging to any cluster |
| `cluster_count` | NUMBER | Number of detected campaigns |
| `total_events` | NUMBER | Total events analyzed |
| `campaign_map` | JSON_OBJECT | GeoJSON FeatureCollection of cluster boundaries |

**Cluster fields:** cluster_id, center_lat, center_lon, radius_km, start_ts, end_ts, duration_hours, event_count, unique_aircraft, dominant_category (spoofing vs jamming), events (array of individual event records), boundary (GeoJSON Polygon convex hull), severity_score

### Logic
1. Query `public.anomaly_events` (29K+ events) filtered by:
   - Time range
   - Geographic area
   - Event types (gps_spoofing, gps_jamming, probable_jamming)
2. Also query `public.kalman_events` for Kalman-detected spoofing events
3. Merge events into unified list with: lat, lon, timestamp, category, hex
4. Run **DBSCAN clustering** with:
   - `eps` derived from `cluster_radius_km` (converted to degrees)
   - `min_samples` = `min_cluster_size`
   - Custom distance metric combining spatial + temporal distance
5. For each cluster:
   - Compute convex hull boundary
   - Count unique affected aircraft
   - Determine dominant event type
   - Score severity (based on size, duration, aircraft count)
6. Return clusters sorted by severity

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| `public.anomaly_events` (local DB, 29K+ rows) | PostgreSQL | Free | N/A |
| `public.kalman_events` (local DB) | PostgreSQL | Free | N/A |
| `public.rule_based_events` (local DB) | PostgreSQL | Free | N/A |

### Implementation Notes
- All three event tables (`anomaly_events`, `kalman_events`, `rule_based_events`) are currently unused — this cube unlocks them
- DBSCAN from scikit-learn with haversine metric is ideal for geographic clustering
- The `region` field in anomaly_events provides pre-computed region labels for quick filtering
- Category: **ANALYSIS**
