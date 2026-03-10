/**
 * ResultsMap — Leaflet map with CartoDB dark tiles, GeoJSON layer,
 * circle markers, bidirectional interaction (flyTo on row select,
 * onMarkerClick on marker click), and auto-fit bounds on data load.
 *
 * Supports three modes:
 *  1. lat/lon only — Point markers from scalar columns
 *  2. lat/lon + geometry — uses geometry objects directly
 *  3. geometry only — renders GeoJSON geometry (LineString, Polygon, etc.)
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

    // If a geometry column exists and contains a valid object, use it directly
    if (geoInfo.geomCol && r[geoInfo.geomCol] && typeof r[geoInfo.geomCol] === 'object') {
      features.push({
        type: 'Feature',
        geometry: r[geoInfo.geomCol] as GeoJSON.Geometry,
        properties: { rowIndex: i },
      });
      return;
    }

    // Fall back to Point from lat/lon scalars
    if (geoInfo.latCol && geoInfo.lonCol) {
      const lat = Number(r[geoInfo.latCol]);
      const lon = Number(r[geoInfo.lonCol]);
      if (isFinite(lat) && isFinite(lon)) {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [lon, lat] },
          properties: { rowIndex: i },
        });
      }
    }
  });

  return { type: 'FeatureCollection', features };
}

// ─── MapController — flyTo selected row ──────────────────────────────────────

interface MapControllerProps {
  geojson: GeoJSON.FeatureCollection;
  rows: unknown[];
  geoInfo: GeoInfo;
  selectedRowIndex: number | null;
}

function MapController({ geojson, rows, geoInfo, selectedRowIndex }: MapControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (selectedRowIndex === null) return;

    // Try lat/lon scalar flyTo first
    if (geoInfo.latCol && geoInfo.lonCol) {
      const row = rows[selectedRowIndex];
      if (typeof row === 'object' && row !== null) {
        const r = row as Record<string, unknown>;
        const lat = Number(r[geoInfo.latCol]);
        const lon = Number(r[geoInfo.lonCol]);
        if (isFinite(lat) && isFinite(lon)) {
          map.flyTo([lat, lon], 10, { animate: true, duration: 0.5 });
          return;
        }
      }
    }

    // Fall back to fitting the geometry bounds of the selected feature
    const feature = geojson.features.find(
      (f) => f.properties?.rowIndex === selectedRowIndex
    );
    if (feature) {
      const layer = L.geoJSON(feature);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        map.flyToBounds(bounds, { padding: [30, 30], animate: true, duration: 0.5 });
      }
    }
  }, [selectedRowIndex, rows, geoInfo, geojson, map]);

  return null;
}

// ─── MapBoundsController — auto-fit all features on load ─────────────────────

interface MapBoundsControllerProps {
  geojson: GeoJSON.FeatureCollection;
}

function MapBoundsController({ geojson }: MapBoundsControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (geojson.features.length === 0) return;

    const layer = L.geoJSON(geojson);
    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [geojson, map]);

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
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
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
      <MapController geojson={geojson} rows={rows} geoInfo={geoInfo} selectedRowIndex={selectedRowIndex} />
      <MapBoundsController geojson={geojson} />
    </MapContainer>
  );
}
