/**
 * PolygonMapWidget — Leaflet overlay for drawing geofence polygons.
 * Renders a full-screen overlay with a dark Leaflet map.
 * Users click to place polygon vertices; Confirm saves as [[lat, lon], ...].
 *
 * PolygonField — button wrapper that opens the overlay.
 * This is what ParamField imports for widget_hint === 'polygon'.
 */

import { useState } from 'react';
import { createPortal } from 'react-dom';
import { MapContainer, TileLayer, Polyline, CircleMarker, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import './PolygonMapWidget.css';

// ── ClickCapture ─────────────────────────────────────────────────────────────

interface ClickCaptureProps {
  onMapClick: (lat: number, lng: number) => void;
}

function ClickCapture({ onMapClick }: ClickCaptureProps) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// ── PolygonMapWidget ──────────────────────────────────────────────────────────

interface PolygonMapWidgetProps {
  initialPolygon?: number[][];
  onConfirm: (polygon: number[][]) => void;
  onClose: () => void;
}

export function PolygonMapWidget({ initialPolygon, onConfirm, onClose }: PolygonMapWidgetProps) {
  const [points, setPoints] = useState<number[][]>(initialPolygon ?? []);

  const addPoint = (lat: number, lng: number) => {
    setPoints((prev) => [...prev, [lat, lng]]);
  };

  const handleClear = () => setPoints([]);

  const handleConfirm = () => {
    onConfirm(points);
    onClose();
  };

  // Close polygon visually by appending first point when 3+ vertices
  const polylinePositions: [number, number][] =
    points.length >= 3
      ? ([...points, points[0]] as [number, number][])
      : (points as [number, number][]);

  return (
    <div
      className="polygon-widget-overlay nodrag nowheel"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="polygon-widget-container">
        <div className="polygon-widget-map">
          <MapContainer
            center={[32, 35]}
            zoom={6}
            style={{ width: '100%', height: '100%' }}
            attributionControl={false}
          >
            <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
            <ClickCapture onMapClick={addPoint} />
            {points.length > 0 && (
              <Polyline
                positions={polylinePositions}
                pathOptions={{ color: '#6366f1', weight: 2 }}
              />
            )}
            {points.map((pt, i) => (
              <CircleMarker
                key={i}
                center={pt as [number, number]}
                radius={6}
                pathOptions={{ color: '#6366f1', fillColor: '#6366f1', fillOpacity: 1 }}
              />
            ))}
          </MapContainer>
        </div>
        <div className="polygon-widget-controls">
          <button
            className="polygon-widget-btn polygon-widget-btn--secondary"
            onClick={handleClear}
          >
            Clear
          </button>
          <button
            className="polygon-widget-btn polygon-widget-btn--secondary"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="polygon-widget-btn polygon-widget-btn--primary"
            onClick={handleConfirm}
            disabled={points.length < 3}
          >
            Confirm ({points.length} pts)
          </button>
        </div>
      </div>
    </div>
  );
}

// ── PolygonField ──────────────────────────────────────────────────────────────

interface PolygonFieldProps {
  value: number[][] | undefined;
  onChange: (value: unknown) => void;
}

export function PolygonField({ value, onChange }: PolygonFieldProps) {
  const [open, setOpen] = useState(false);

  const hasPoints = Array.isArray(value) && value.length > 0;

  return (
    <>
      <button
        className="polygon-field-btn nodrag nowheel"
        onClick={() => setOpen(true)}
      >
        {hasPoints ? (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginRight: 4 }}>
              <path d="M1 9L4 2l3 5 2-2.5L11 9H1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            </svg>
            Geofence ({value!.length} pts)
          </>
        ) : (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginRight: 4 }}>
              <path d="M1 9L4 2l3 5 2-2.5L11 9H1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            </svg>
            Draw geofence
          </>
        )}
      </button>
      {open && createPortal(
        <PolygonMapWidget
          initialPolygon={value}
          onConfirm={onChange}
          onClose={() => setOpen(false)}
        />,
        document.body
      )}
    </>
  );
}
