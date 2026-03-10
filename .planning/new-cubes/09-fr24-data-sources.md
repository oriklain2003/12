# Category IX: FlightRadar24 API Data Source Cubes

These cubes serve as primary data sources powered by the FR24 API, bringing external real-time and historical flight data into the workflow builder.

## FR24 Integration Architecture

All FR24 cubes share a common pattern:
- Use the official `fr24sdk` Python package
- Authenticate via `FR24_API_TOKEN` environment variable (added to `.env`)
- Respect credit budgets (each call costs credits based on subscription tier)
- Cache responses where appropriate to minimize credit usage

---

## 27. `fr24_live_flights` — Real-Time Flight Positions

**Purpose:** Query FlightRadar24 for current live flight positions worldwide. Provides access to flights outside your ADS-B receiver coverage, with rich metadata including airline, aircraft type, and category.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `polygon` | JSON_OBJECT | No | Geographic bounds [[lat, lon], ...] |
| `bounds` | JSON_OBJECT | No | Alternative: {north, south, east, west} bounding box |
| `callsigns` | LIST_OF_STRINGS | No | Filter by callsign(s) |
| `registrations` | LIST_OF_STRINGS | No | Filter by registration(s) |
| `aircraft_type` | STRING | No | ICAO aircraft type code (e.g., "B738") |
| `airport` | STRING | No | Filter flights to/from this airport (ICAO/IATA) |
| `airline` | STRING | No | ICAO airline code |
| `min_altitude` | NUMBER | No | Minimum altitude in feet |
| `max_altitude` | NUMBER | No | Maximum altitude in feet |
| `category` | LIST_OF_STRINGS | No | Aircraft categories to include |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `flights` | JSON_OBJECT | Array of live flight position records |
| `flight_ids` | LIST_OF_STRINGS | FR24 flight hex IDs |
| `count` | NUMBER | Number of flights returned |
| `map_data` | JSON_OBJECT | GeoJSON FeatureCollection of flight positions |

**Flight record fields:** flight_id, callsign, registration, aircraft_type, airline_icao, airline_name, origin, destination, latitude, longitude, altitude_ft, ground_speed_kts, heading, vertical_speed, squawk, timestamp, on_ground, category

### Logic
1. Convert polygon input to FR24 bounds format if needed
2. Call `fr24sdk` → `client.live.get_flights_positions_full()` with filters
3. Transform response into standard output format
4. Generate GeoJSON points for map rendering
5. Extract flight IDs for downstream processing

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_live_flights_positions_full`) | REST API | Credits per call | Up to 30,000 results |

### Implementation Notes
- Up to 30,000 flights per call
- Full mode includes all metadata; light mode is cheaper on credits
- Cache live positions with short TTL (30 seconds)
- Category: **DATA_SOURCE**

---

## 28. `fr24_flight_history` — Historical Flight Positions

**Purpose:** Query FR24 for historical flight positions at a specific point in time. Provides a "time machine" view of the sky — data available back to May 2016 with up to 5-second resolution.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `target_timestamp` | STRING | Yes | Epoch seconds or ISO datetime — the moment to query |
| `polygon` | JSON_OBJECT | No | Geographic bounds [[lat, lon], ...] |
| `bounds` | JSON_OBJECT | No | {north, south, east, west} bounding box |
| `callsigns` | LIST_OF_STRINGS | No | Filter by callsign(s) |
| `registrations` | LIST_OF_STRINGS | No | Filter by registration(s) |
| `aircraft_type` | STRING | No | ICAO type code filter |
| `airport` | STRING | No | Flights to/from this airport |
| `min_altitude` | NUMBER | No | Minimum altitude in feet |
| `max_altitude` | NUMBER | No | Maximum altitude in feet |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `flights` | JSON_OBJECT | Array of flight positions at the target time |
| `flight_ids` | LIST_OF_STRINGS | FR24 flight hex IDs |
| `count` | NUMBER | Number of flights captured |
| `map_data` | JSON_OBJECT | GeoJSON FeatureCollection snapshot |
| `timestamp` | STRING | Actual timestamp of data (may differ slightly from request) |

### Logic
1. Parse `target_timestamp` to epoch seconds
2. Convert polygon to bounds if needed
3. Call `fr24sdk` → `client.historic.get_flights_positions_full()` with timestamp and filters
4. Transform and return

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_historic_flights_positions_full`) | REST API | Credits per call | Historical data from May 11, 2016 |

### Implementation Notes
- Historical resolution varies by age: recent data up to 5-second intervals, older data may be sparser
- Extremely powerful for investigations: "What was flying over X at time Y?"
- Cache historical queries aggressively (data doesn't change)
- Category: **DATA_SOURCE**

---

## 29. `fr24_flight_summary` — Flight Takeoff/Landing Details

**Purpose:** Get comprehensive flight summary data from FR24 including scheduled vs actual times, gates, airlines, and full route details. The richest metadata endpoint for flight-level analysis.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `start_date` | STRING | No | Start of date range (ISO date) |
| `end_date` | STRING | No | End of date range (ISO date) |
| `callsigns` | LIST_OF_STRINGS | No | Filter by callsign(s) |
| `registrations` | LIST_OF_STRINGS | No | Filter by registration(s) |
| `airport` | STRING | No | Flights to/from this airport |
| `route` | STRING | No | Specific route "ORIGIN-DESTINATION" (ICAO codes) |
| `aircraft_type` | STRING | No | ICAO type code |
| `airline` | STRING | No | ICAO airline code |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `flights` | JSON_OBJECT | Array of flight summary records |
| `flight_ids` | LIST_OF_STRINGS | FR24 flight hex IDs |
| `count` | NUMBER | Number of flights |

**Summary record fields:** flight_id, callsign, flight_number, registration, aircraft_type, airline_icao, airline_name, origin_icao, origin_iata, destination_icao, destination_iata, scheduled_departure, actual_departure, scheduled_arrival, actual_arrival, status (landed/in_air/scheduled), delay_minutes, distance_nm, duration_minutes

### Logic
1. Build query parameters from inputs
2. Call `fr24sdk` → `client.flight_summary.get_flight_summary_full()` with filters
3. Transform and return

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_flight_summary_full`) | REST API | Credits per call | Up to 20,000 results |

### Implementation Notes
- Key cube for `pattern_of_life` analysis (feeds baseline computation)
- Scheduled vs actual time comparison reveals delays, diversions
- Route data enables network analysis
- Category: **DATA_SOURCE**

---

## 30. `fr24_flight_tracks` — Detailed Position Trail

**Purpose:** Get the complete position trail for a specific flight from FR24. Higher resolution than your local DB may have (up to 5-second intervals for recent flights).

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `flight_id` | STRING | Yes | FR24 flight hex ID |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `tracks` | JSON_OBJECT | Array of position records |
| `flight_id` | STRING | The queried flight ID |
| `point_count` | NUMBER | Number of track points |
| `map_data` | JSON_OBJECT | GeoJSON LineString of the track |
| `duration_minutes` | NUMBER | Flight duration |
| `distance_nm` | NUMBER | Total distance traveled |

**Track point fields:** timestamp, latitude, longitude, altitude_ft, ground_speed_kts, heading, vertical_speed_fpm, squawk, on_ground

### Logic
1. Call `fr24sdk` → `client.flight_tracks.get_flight_tracks()` with flight ID
2. Transform response into track point array
3. Compute derived values: total distance, duration
4. Generate GeoJSON LineString for map rendering

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_flight_tracks`) | REST API | Credits per call | Per flight |

### Implementation Notes
- One flight at a time — for bulk track retrieval, use local DB or FR24 historical positions
- Resolution: up to 5-second intervals for recent flights
- Useful for detailed analysis of specific suspicious flights
- Category: **DATA_SOURCE**

---

## 31. `fr24_airline_info` — Airline Reference Data

**Purpose:** Look up airline details by ICAO code. Enrichment cube for adding airline context to flight data.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airline_codes` | LIST_OF_STRINGS | Yes | ICAO airline codes to look up |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `airlines` | JSON_OBJECT | Array of airline detail records |
| `count` | NUMBER | Number of airlines returned |

**Airline record fields:** icao_code, iata_code, name, country, callsign_prefix, fleet_size, active

### Logic
1. For each airline code: call `fr24sdk` → `client.airlines.get_airline_info()`
2. Aggregate and return

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_airline_info`) | REST API | Credits per call | Per airline |

### Implementation Notes
- Cache aggressively — airline data rarely changes (TTL: 7 days)
- Category: **DATA_SOURCE** (reference)

---

## 32. `fr24_airport_info` — Airport Reference Data

**Purpose:** Get airport details from FR24 including location, elevation, timezone, and operational info. Complements `airport_enrichment` (OurAirports) with FR24-specific data.

### Inputs
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `airport_codes` | LIST_OF_STRINGS | Yes | ICAO or IATA codes |

### Outputs
| Name | Type | Description |
|------|------|-------------|
| `airports` | JSON_OBJECT | Array of airport detail records |
| `count` | NUMBER | Number of airports returned |
| `map_data` | JSON_OBJECT | GeoJSON points |

**Airport record fields:** icao_code, iata_code, name, city, country, latitude, longitude, elevation_ft, timezone, website

### Logic
1. For each airport code: call `fr24sdk` → `client.airports.get_airport_info_full()`
2. Generate GeoJSON and return

### Data Sources
| Source | Type | Cost | Rate Limit |
|--------|------|------|------------|
| **FR24 API** (`get_airport_info_full`) | REST API | Credits per call | Per airport |

### Implementation Notes
- Cache aggressively (TTL: 7 days)
- Use `airport_enrichment` (OurAirports, free) as primary; this cube supplements with FR24-specific data
- Category: **DATA_SOURCE** (reference)
