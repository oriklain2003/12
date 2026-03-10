# Category VI: Weather & Environment Correlation Cubes

## 18. `weather_enrichment` — Aviation Weather Lookup

**Purpose:** Enrich flight data with weather conditions at departure/arrival airports or along the route. Enables analysts to determine whether flight anomalies (diversions, holding patterns, altitude changes) are weather-related or require further investigation.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airport_codes` | LIST_OF_STRINGS | No | ICAO codes to fetch weather for |
| `full_result` | JSON_OBJECT | No | Accepts full result — extracts origin/destination airports |
| `flight_ids` | LIST_OF_STRINGS | No | Flight IDs (resolved to airports via flight_metadata) |
| `include_taf` | BOOLEAN | No | Include forecast data (default: true) |
| `include_metar` | BOOLEAN | No | Include current/recent observations (default: true) |
| `hours_back` | NUMBER | No | METAR history lookback (default: 6) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `weather` | JSON_OBJECT | Array of weather records per airport |
| `low_visibility_airports` | LIST_OF_STRINGS | Airports with visibility < 3 SM |
| `severe_weather_airports` | LIST_OF_STRINGS | Airports with thunderstorms, icing, or turbulence |
| `weather_summary` | JSON_OBJECT | Quick overview: worst conditions, ceiling/vis ranges |

**Weather record fields:** airport_icao, observation_time, temperature_c, dewpoint_c, wind_direction_deg, wind_speed_kts, wind_gust_kts, visibility_sm, ceiling_ft, flight_category (VFR/MVFR/IFR/LIFR), weather_phenomena (rain/snow/fog/thunderstorm), altimeter_inhg, raw_metar, taf_text

### Logic
1. Resolve inputs to ICAO airport codes:
   - From `airport_codes` directly
   - From `full_result` extracting origin_airport/destination_airport fields
   - From `flight_ids` via `research.flight_metadata` or `live.flight_metadata`
2. Query **aviationweather.gov API**:
   - METAR: `GET /api/data/metar?ids={codes}&format=json&hours={hours_back}`
   - TAF: `GET /api/data/taf?ids={codes}&format=json`
3. Parse responses into structured weather records
4. Classify flight category: VFR (ceiling > 3000, vis > 5), MVFR, IFR, LIFR
5. Flag airports with severe conditions
6. Return organized weather data

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **aviationweather.gov** | REST API | Free, no key required | Reasonable use |

### Implementation Notes
- aviationweather.gov is authoritative (NOAA/NWS) and completely free
- METAR observations are issued hourly (or more in changing conditions)
- TAF forecasts cover 24-30 hours ahead
- Cache responses with short TTL (15 minutes for METAR, 1 hour for TAF)
- Category: **ANALYSIS** (enrichment)

---

## 19. `fire_detection_overlay` — NASA FIRMS Hotspot Correlation

**Purpose:** Overlay satellite-detected thermal hotspots (fires, explosions) near airports, military bases, or flight routes. Detect potential airstrikes, facility fires, or environmental hazards that correlate with flight activity.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | No | Area of interest [[lat, lon], ...] |
| `airport_codes` | LIST_OF_STRINGS | No | ICAO codes — search within radius of each |
| `radius_km` | NUMBER | No | Search radius around airports (default: 25) |
| `time_range_days` | NUMBER | No | Lookback period (default: 7) |
| `min_confidence` | NUMBER | No | Minimum detection confidence 0-100 (default: 70) |
| `satellite` | STRING | No | Satellite source: `"VIIRS"`, `"MODIS"`, `"all"` (default: `"VIIRS"`) |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `hotspots` | JSON_OBJECT | Array of fire/thermal detection records |
| `affected_airports` | LIST_OF_STRINGS | Airports with nearby hotspots |
| `clusters` | JSON_OBJECT | Grouped hotspots by proximity |
| `map_data` | JSON_OBJECT | GeoJSON FeatureCollection for visualization |
| `count` | NUMBER | Total hotspot detections |

**Hotspot fields:** latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, frp (fire radiative power), daynight, distance_to_nearest_airport_km, nearest_airport

### Logic
1. Resolve geographic area from polygon or airport codes + radius
2. Query **NASA FIRMS API**:
   - `GET https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{area}/{days}`
   - Source: VIIRS_SNPP_NRT, MODIS_NRT, etc.
3. Parse CSV response into structured records
4. Filter by confidence threshold
5. For each hotspot:
   - Compute distance to nearest airport (from OurAirports data or local)
   - Cluster nearby detections (same fire detected multiple times)
6. Generate GeoJSON for map overlay
7. Flag airports with unusual thermal activity

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **NASA FIRMS** (`firms.modaps.eosdis.nasa.gov`) | REST API | Free (MAP_KEY via email registration) | 10 requests/minute |
| Airport coordinates (OurAirports or local) | CSV/Static | Free | N/A |

### Implementation Notes
- FIRMS provides near-real-time data (3-hour latency for NRT products)
- Historical data available back to November 2000
- VIIRS has better spatial resolution (375m) than MODIS (1km)
- Fire Radiative Power (FRP) can distinguish industrial fires from wildfires from explosions
- Very powerful for conflict monitoring — airstrikes create distinctive thermal signatures
- Category: **ANALYSIS**
