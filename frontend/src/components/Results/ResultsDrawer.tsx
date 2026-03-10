/**
 * ResultsDrawer — orchestrates results display in a slide-up panel.
 *
 * Shows a resizable table+map split layout when geo data is detected,
 * or full-width table when there are no geo columns. Bidirectional
 * interaction: row select -> map flyTo, marker click -> row highlight.
 *
 * For cubes with a `widget` field, renders custom visualization components
 * instead of (or in addition to) the default ResultsMap.
 *
 * Selection state is LOCAL (not Zustand) — ephemeral view state.
 * The only thing from the store is selectedResultNodeId and results.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { ResultsTable } from './ResultsTable';
import { ResultsMap } from './ResultsMap';
import { GeoPlaybackWidget } from '../Visualization/GeoPlaybackWidget';
import { detectGeoColumns } from '../../utils/geoDetect';
import type { GeoInfo } from '../../utils/geoDetect';
import { useFlowStore } from '../../store/flowStore';
import './ResultsDrawer.css';

// ─── ResizeDivider ────────────────────────────────────────────────────────────

interface ResizeDividerProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  onSplitChange: (ratio: number) => void;
}

function ResizeDivider({ containerRef, onSplitChange }: ResizeDividerProps) {
  const isDragging = useRef(false);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    isDragging.current = true;
    (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const clamped = Math.min(0.85, Math.max(0.15, ratio));
    onSplitChange(clamped);
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    isDragging.current = false;
    (e.currentTarget as HTMLDivElement).releasePointerCapture(e.pointerId);
  };

  return (
    <div
      className="results-drawer__divider"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    />
  );
}

// ─── ResultsDrawer ────────────────────────────────────────────────────────────

export function ResultsDrawer() {
  // Ephemeral view state — local only
  const [selectedRowIndex, setSelectedRowIndex] = useState<number | null>(null);
  const [splitRatio, setSplitRatio] = useState(0.55);

  const contentRef = useRef<HTMLDivElement>(null);

  // Store reads
  const selectedNodeId = useFlowStore((s) => s.selectedResultNodeId);
  const setSelectedResultNodeId = useFlowStore((s) => s.setSelectedResultNodeId);
  const results = useFlowStore((s) =>
    s.selectedResultNodeId ? s.results[s.selectedResultNodeId] ?? null : null
  );
  const cubeName = useFlowStore((s) => {
    const node = s.nodes.find((n) => n.id === s.selectedResultNodeId);
    return node?.data.cubeDef.name ?? 'Results';
  });
  const cubeWidget = useFlowStore((s) => {
    const node = s.nodes.find((n) => n.id === s.selectedResultNodeId);
    return node?.data.cubeDef.widget ?? null;
  });
  const cubeParams = useFlowStore(
    useShallow((s) => {
      const node = s.nodes.find((n) => n.id === s.selectedResultNodeId);
      return node?.data.params ?? {};
    })
  );

  // Derived
  const geoInfo: GeoInfo | null = useMemo(
    () => (results ? detectGeoColumns(results.rows) : null),
    [results]
  );

  const isOpen = selectedNodeId !== null && results !== null && results.rows.length > 0;

  // Reset row selection when selected cube changes
  useEffect(() => {
    setSelectedRowIndex(null);
  }, [selectedNodeId]);

  return (
    <div className={`results-drawer${isOpen ? ' results-drawer--open' : ''}`}>
      {/* Handle / grip — click to close */}
      <div className="results-drawer__handle" onClick={() => setSelectedResultNodeId(null)}>
        <div className="results-drawer__grip" />
      </div>

      {/* Header */}
      <div className="results-drawer__header">
        <span className="results-drawer__title">{cubeName} Results</span>
        <button
          className="results-drawer__close"
          onClick={() => setSelectedResultNodeId(null)}
        >
          Close
        </button>
      </div>

      {/* Content — table + optional map */}
      <div className="results-drawer__content" ref={contentRef}>
        {results && (
          <>
            <div
              className="results-drawer__table-pane"
              style={{ flex: (cubeWidget || geoInfo) ? `0 0 ${splitRatio * 100}%` : '1' }}
            >
              <ResultsTable
                rows={results.rows}
                truncated={results.truncated}
                selectedRowIndex={selectedRowIndex}
                onRowSelect={setSelectedRowIndex}
              />
            </div>

            {(cubeWidget || geoInfo) && (
              <>
                <ResizeDivider containerRef={contentRef} onSplitChange={setSplitRatio} />
                <div className="results-drawer__map-pane" style={{ flex: 1 }}>
                  {cubeWidget === 'geo_playback' ? (
                    <GeoPlaybackWidget rows={results.rows} params={cubeParams} />
                  ) : geoInfo ? (
                    <ResultsMap
                      rows={results.rows}
                      geoInfo={geoInfo}
                      selectedRowIndex={selectedRowIndex}
                      onMarkerClick={setSelectedRowIndex}
                    />
                  ) : null}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
