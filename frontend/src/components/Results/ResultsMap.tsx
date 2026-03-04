/**
 * ResultsMap — Leaflet map with CartoDB dark tiles, GeoJSON layer,
 * circle markers, bidirectional interaction (flyTo on row select,
 * onMarkerClick on marker click), and auto-fit bounds on data load.
 */

import { useMemo, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoInfo } from '../../utils/geoDetect';
import './ResultsMap.css';

// ─── Vite Leaflet icon fix ────────────────────────────────────────────────────
// Vite processes assets, so the default icon URLs resolve incorrectly.
// Override prototype options with explicit imports.

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.prototype.options.iconUrl = markerIconUrl;
L.Icon.Default.prototype.options.iconRetinaUrl = markerIconRetinaUrl;
L.Icon.Default.prototype.options.shadowUrl = markerShadowUrl;
L.Icon.Default.imagePath = '';

// ─── Props ────────────────────────────────────────────────────────────────────

interface ResultsMapProps {
  rows: unknown[];
  geoInfo: GeoInfo;
  selectedRowIndex: number | null;
  onMarkerClick: (index: number) => void;
}

// ─── GeoJSON builder ──────────────────────────────────────────────────────────

function buildGeoJSON(
  rows: unknown[],
  geoInfo: GeoInfo
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  rows.forEach((row, i) => {
    if (typeof row !== 'object' || row === null) return;
    const r = row as Record<string, unknown>;

    const lat = Number(r[geoInfo.latCol]);
    const lon = Number(r[geoInfo.lonCol]);

    if (!isFinite(lat) || !isFinite(lon)) return;

    // If a geometry column exists and contains a valid object, use it directly
    if (geoInfo.geomCol && r[geoInfo.geomCol] && typeof r[geoInfo.geomCol] === 'object') {
      features.push({
        type: 'Feature',
        geometry: r[geoInfo.geomCol] as GeoJSON.Geometry,
        properties: { rowIndex: i },
      });
    } else {
      // Default: Point geometry — GeoJSON uses [lon, lat] order
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [lon, lat],
        },
        properties: { rowIndex: i },
      });
    }
  });

  return { type: 'FeatureCollection', features };
}

// ─── MapController — flyTo selected row ──────────────────────────────────────

interface MapControllerProps {
  rows: unknown[];
  geoInfo: GeoInfo;
  selectedRowIndex: number | null;
}

function MapController({ rows, geoInfo, selectedRowIndex }: MapControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (selectedRowIndex === null) return;
    const row = rows[selectedRowIndex];
    if (typeof row !== 'object' || row === null) return;

    const r = row as Record<string, unknown>;
    const lat = Number(r[geoInfo.latCol]);
    const lon = Number(r[geoInfo.lonCol]);

    if (isFinite(lat) && isFinite(lon)) {
      map.flyTo([lat, lon], 10, { animate: true, duration: 0.5 });
    }
  }, [selectedRowIndex, rows, geoInfo, map]);

  return null;
}

// ─── MapBoundsController — auto-fit all markers on load ──────────────────────

interface MapBoundsControllerProps {
  rows: unknown[];
  geoInfo: GeoInfo;
}

function MapBoundsController({ rows, geoInfo }: MapBoundsControllerProps) {
  const map = useMap();

  useEffect(() => {
    const points: [number, number][] = [];

    for (const row of rows) {
      if (typeof row !== 'object' || row === null) continue;
      const r = row as Record<string, unknown>;
      const lat = Number(r[geoInfo.latCol]);
      const lon = Number(r[geoInfo.lonCol]);
      if (isFinite(lat) && isFinite(lon)) {
        points.push([lat, lon]);
      }
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [rows, geoInfo, map]);

  return null;
}

// ─── Main component ───────────────────────────────────────────────────────────

export function ResultsMap({ rows, geoInfo, selectedRowIndex, onMarkerClick }: ResultsMapProps) {
  const geojson = useMemo(() => buildGeoJSON(rows, geoInfo), [rows, geoInfo]);

  return (
    // Do NOT put a key on MapContainer — prevents flash when switching cubes (Pitfall 3)
    <MapContainer
      center={[20, 0]}
      zoom={2}
      className="results-map"
      zoomControl={true}
    >
      {/* CartoDB dark tiles */}
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        subdomains={['a', 'b', 'c', 'd']}
        maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      />

      {/* GeoJSON layer — keyed to force re-mount on data change (Pitfall 2) */}
      <GeoJSON
        key={JSON.stringify(geojson)}
        data={geojson}
        pointToLayer={(_feature, latlng) =>
          L.circleMarker(latlng, {
            radius: 6,
            fillColor: '#6366f1',
            color: '#818cf8',
            weight: 1.5,
            opacity: 1,
            fillOpacity: 0.7,
          })
        }
        onEachFeature={(feature, layer) => {
          layer.on('click', () => {
            if (feature.properties?.rowIndex !== undefined) {
              onMarkerClick(feature.properties.rowIndex as number);
            }
          });
        }}
        style={() => ({
          color: '#6366f1',
          fillColor: '#6366f1',
          weight: 1.5,
          fillOpacity: 0.3,
        })}
      />

      {/* Controllers must be inside MapContainer to access map context */}
      <MapController rows={rows} geoInfo={geoInfo} selectedRowIndex={selectedRowIndex} />
      <MapBoundsController rows={rows} geoInfo={geoInfo} />
    </MapContainer>
  );
}
