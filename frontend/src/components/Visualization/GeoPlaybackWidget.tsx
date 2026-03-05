/**
 * GeoPlaybackWidget — animated Leaflet map with dual-handle timeline slider,
 * density histogram, play/pause controls, and speed selector.
 *
 * Renders geo-temporal data animating over time on a map. Objects appear and
 * disappear instantly as they enter/leave the time window. Auto-colored by
 * id_column or color_by_column. No labels, trails, ghost effects, or size variation.
 */

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './GeoPlaybackWidget.css';

// ─── Leaflet icon fix ─────────────────────────────────────────────────────────

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.prototype.options.iconUrl = markerIconUrl;
L.Icon.Default.prototype.options.iconRetinaUrl = markerIconRetinaUrl;
L.Icon.Default.prototype.options.shadowUrl = markerShadowUrl;
L.Icon.Default.imagePath = '';

// ─── Constants ────────────────────────────────────────────────────────────────

// D3 Tableau10 colors — no D3 dependency
const COLORS = [
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
];

const HISTOGRAM_BUCKETS = 100;
const ANIMATION_INTERVAL_MS = 100; // 10 FPS

// ─── Types ────────────────────────────────────────────────────────────────────

export interface GeoPlaybackWidgetProps {
  rows: unknown[];
  params: Record<string, unknown>;
}

// ─── MapBoundsController — auto-fit all rows on mount ────────────────────────

interface MapBoundsControllerProps {
  rows: unknown[];
  geometryCol: string;
}

function MapBoundsController({ rows, geometryCol }: MapBoundsControllerProps) {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];

    for (const row of rows) {
      if (typeof row !== 'object' || row === null) continue;
      const r = row as Record<string, unknown>;
      const geom = r[geometryCol];
      if (geom && typeof geom === 'object') {
        const g = geom as Record<string, unknown>;
        // Point geometry: coordinates = [lon, lat]
        if (g.type === 'Point' && Array.isArray(g.coordinates) && g.coordinates.length >= 2) {
          const lon = Number(g.coordinates[0]);
          const lat = Number(g.coordinates[1]);
          if (isFinite(lat) && isFinite(lon)) {
            points.push([lat, lon]);
          }
        }
        // LineString: extract all coords
        else if (g.type === 'LineString' && Array.isArray(g.coordinates)) {
          for (const coord of g.coordinates as unknown[]) {
            if (Array.isArray(coord) && coord.length >= 2) {
              const lon = Number(coord[0]);
              const lat = Number(coord[1]);
              if (isFinite(lat) && isFinite(lon)) {
                points.push([lat, lon]);
              }
            }
          }
        }
      }
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [30, 30] });
    }
    // Only run on mount — ignore row/col changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTimestamp(ts: number): string {
  // If epoch seconds (between year 2000 and 2100 in unix seconds)
  if (ts > 946684800 && ts < 4102444800) {
    return new Date(ts * 1000).toISOString().slice(0, 19).replace('T', ' ');
  }
  // If epoch milliseconds
  if (ts > 946684800000 && ts < 4102444800000) {
    return new Date(ts).toISOString().slice(0, 19).replace('T', ' ');
  }
  return String(ts);
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function GeoPlaybackWidget({ rows, params }: GeoPlaybackWidgetProps) {
  // Extract params with defaults
  const geometryCol = String(params.geometry_column ?? 'geometry');
  const timestampCol = String(params.timestamp_column ?? 'timestamp');
  const idCol = params.id_column ? String(params.id_column) : undefined;
  const colorByCol = params.color_by_column ? String(params.color_by_column) : undefined;

  // ── Data validation ─────────────────────────────────────────────────────────

  // Guard: empty data
  if (rows.length === 0) {
    return (
      <div className="geo-playback geo-playback--empty">
        <span>No data to playback</span>
      </div>
    );
  }

  // Check columns exist in first row
  const firstRow = rows[0] as Record<string, unknown>;
  if (!(timestampCol in firstRow)) {
    return (
      <div className="geo-playback geo-playback--empty">
        <span>Timestamp column &apos;{timestampCol}&apos; not found in data</span>
      </div>
    );
  }
  if (!(geometryCol in firstRow)) {
    return (
      <div className="geo-playback geo-playback--empty">
        <span>Geometry column &apos;{geometryCol}&apos; not found in data</span>
      </div>
    );
  }

  return (
    <GeoPlaybackInner
      rows={rows}
      geometryCol={geometryCol}
      timestampCol={timestampCol}
      idCol={idCol}
      colorByCol={colorByCol}
    />
  );
}

// ─── Inner component (only rendered when data is valid) ───────────────────────

interface InnerProps {
  rows: unknown[];
  geometryCol: string;
  timestampCol: string;
  idCol: string | undefined;
  colorByCol: string | undefined;
}

function GeoPlaybackInner({ rows, geometryCol, timestampCol, idCol, colorByCol }: InnerProps) {
  // ── Timestamp range ─────────────────────────────────────────────────────────

  const { tsMin, tsMax } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const row of rows) {
      if (typeof row !== 'object' || row === null) continue;
      const ts = Number((row as Record<string, unknown>)[timestampCol]);
      if (isFinite(ts)) {
        if (ts < min) min = ts;
        if (ts > max) max = ts;
      }
    }
    if (!isFinite(min)) min = 0;
    if (!isFinite(max)) max = min;
    if (min === max) max = min + 1;
    return { tsMin: min, tsMax: max };
  }, [rows, timestampCol]);

  const windowSize = (tsMax - tsMin) * 0.05;

  // ── Animation state ─────────────────────────────────────────────────────────

  const [windowStart, setWindowStart] = useState(tsMin);
  const [windowEnd, setWindowEnd] = useState(tsMin + windowSize);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const speedRef = useRef(speed);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Keep speedRef in sync without re-triggering animation effect
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  // Reset window when rows change
  useEffect(() => {
    setWindowStart(tsMin);
    setWindowEnd(tsMin + windowSize);
    setPlaying(false);
  }, [tsMin, tsMax, windowSize]);

  // Animation loop
  useEffect(() => {
    if (!playing) {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    timerRef.current = setInterval(() => {
      const step = (tsMax - tsMin) * 0.002 * speedRef.current;
      setWindowStart((prev) => {
        const next = prev + step;
        if (next > tsMax) return tsMin;
        return next;
      });
      setWindowEnd((prev) => {
        const next = prev + step;
        if (next > tsMax) return tsMin + (tsMax - tsMin) * 0.05;
        return next;
      });
    }, ANIMATION_INTERVAL_MS);

    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playing, tsMin, tsMax]);

  // ── Color assignment ────────────────────────────────────────────────────────

  const colorMap = useMemo<Map<string, string>>(() => {
    const colorKey = colorByCol ?? idCol;
    const map = new Map<string, string>();
    if (!colorKey) return map;

    let i = 0;
    for (const row of rows) {
      if (typeof row !== 'object' || row === null) continue;
      const val = String((row as Record<string, unknown>)[colorKey] ?? '');
      if (!map.has(val)) {
        map.set(val, COLORS[i % COLORS.length]);
        i++;
      }
    }
    return map;
  }, [rows, idCol, colorByCol]);

  const defaultColor = COLORS[0];

  const getColor = useCallback(
    (row: Record<string, unknown>): string => {
      const colorKey = colorByCol ?? idCol;
      if (!colorKey) return defaultColor;
      const val = String(row[colorKey] ?? '');
      return colorMap.get(val) ?? defaultColor;
    },
    [colorMap, colorByCol, idCol, defaultColor]
  );

  // ── Density histogram ───────────────────────────────────────────────────────

  const histogram = useMemo<number[]>(() => {
    const buckets = new Array<number>(HISTOGRAM_BUCKETS).fill(0);
    const range = tsMax - tsMin;
    if (range === 0) return buckets;

    for (const row of rows) {
      if (typeof row !== 'object' || row === null) continue;
      const ts = Number((row as Record<string, unknown>)[timestampCol]);
      if (!isFinite(ts)) continue;
      const bucketIdx = Math.min(
        HISTOGRAM_BUCKETS - 1,
        Math.floor(((ts - tsMin) / range) * HISTOGRAM_BUCKETS)
      );
      buckets[bucketIdx]++;
    }

    const maxCount = Math.max(...buckets);
    if (maxCount === 0) return buckets;
    return buckets.map((v) => v / maxCount);
  }, [rows, tsMin, tsMax, timestampCol]);

  // ── Visible rows filtering ──────────────────────────────────────────────────

  const visibleRows = useMemo(() => {
    return rows.filter((row) => {
      if (typeof row !== 'object' || row === null) return false;
      const ts = Number((row as Record<string, unknown>)[timestampCol]);
      return isFinite(ts) && ts >= windowStart && ts <= windowEnd;
    });
  }, [rows, timestampCol, windowStart, windowEnd]);

  // ── GeoJSON construction ────────────────────────────────────────────────────

  const geojson = useMemo<GeoJSON.FeatureCollection>(() => {
    const features: GeoJSON.Feature[] = [];

    for (const row of visibleRows) {
      if (typeof row !== 'object' || row === null) continue;
      const r = row as Record<string, unknown>;
      const geom = r[geometryCol];

      if (!geom || typeof geom !== 'object') continue;

      const color = getColor(r);

      features.push({
        type: 'Feature',
        geometry: geom as GeoJSON.Geometry,
        properties: { color },
      });
    }

    return { type: 'FeatureCollection', features };
  }, [visibleRows, geometryCol, getColor]);

  // ── Timeline handle handlers ────────────────────────────────────────────────

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setWindowStart(Math.min(val, windowEnd));
  };

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setWindowEnd(Math.max(val, windowStart));
  };

  const step = (tsMax - tsMin) / 1000;

  // ── Single timestamp: show static view ─────────────────────────────────────

  const isSingleTimestamp = tsMax - tsMin <= 1;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="geo-playback">
      {/* Map */}
      <div className="geo-playback__map">
        <MapContainer
          center={[20, 0]}
          zoom={2}
          className="geo-playback__leaflet"
          zoomControl={true}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            subdomains={['a', 'b', 'c', 'd']}
            maxZoom={19}
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />

          {/* GeoJSON layer — keyed to force re-mount on window change */}
          <GeoJSON
            key={`${windowStart}-${windowEnd}`}
            data={geojson}
            pointToLayer={(_feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 5,
                fillColor: (_feature.properties?.color as string) ?? defaultColor,
                color: '#ffffff',
                weight: 1,
                opacity: 0.6,
                fillOpacity: 0.85,
              })
            }
            style={(feature) => ({
              color: (feature?.properties?.color as string) ?? defaultColor,
              weight: 2,
              fillOpacity: 0.3,
            })}
          />

          {/* Auto-fit bounds to ALL rows on mount */}
          <MapBoundsController rows={rows} geometryCol={geometryCol} />
        </MapContainer>
      </div>

      {/* Timeline */}
      <div className="geo-playback__timeline">
        {/* Density histogram SVG — behind the sliders */}
        <svg
          className="geo-playback__histogram"
          viewBox={`0 0 ${HISTOGRAM_BUCKETS} 1`}
          preserveAspectRatio="none"
        >
          {histogram.map((value, i) => (
            <rect
              key={i}
              x={i}
              y={1 - value}
              width={1}
              height={value}
              fill="var(--accent, #6366f1)"
            />
          ))}
        </svg>

        {/* Dual-handle range track */}
        <div className="geo-playback__range-track">
          <input
            type="range"
            min={tsMin}
            max={tsMax}
            step={step}
            value={windowStart}
            onChange={handleStartChange}
            disabled={isSingleTimestamp}
            className="geo-playback__range geo-playback__range--start"
          />
          <input
            type="range"
            min={tsMin}
            max={tsMax}
            step={step}
            value={windowEnd}
            onChange={handleEndChange}
            disabled={isSingleTimestamp}
            className="geo-playback__range geo-playback__range--end"
          />
        </div>

        {/* Controls row */}
        <div className="geo-playback__controls">
          {/* Play / Pause */}
          <button
            className="geo-playback__play-btn"
            onClick={() => setPlaying((p) => !p)}
            disabled={isSingleTimestamp}
            title={playing ? 'Pause' : 'Play'}
          >
            {playing ? '\u23F8' : '\u25B6'}
          </button>

          {/* Speed selector */}
          <div className="geo-playback__speed-group">
            {([1, 2, 5, 10] as const).map((s) => (
              <button
                key={s}
                className={`geo-playback__speed-btn${speed === s ? ' geo-playback__speed-btn--active' : ''}`}
                onClick={() => setSpeed(s)}
                disabled={isSingleTimestamp}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Time window display */}
          <span className="geo-playback__time-display">
            {isSingleTimestamp
              ? formatTimestamp(tsMin)
              : `${formatTimestamp(windowStart)} \u2014 ${formatTimestamp(windowEnd)}`}
          </span>

          {/* Visible count */}
          <span className="geo-playback__count">
            {visibleRows.length} / {rows.length}
          </span>
        </div>
      </div>
    </div>
  );
}
