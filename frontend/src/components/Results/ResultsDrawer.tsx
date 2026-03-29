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

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { useShallow } from 'zustand/react/shallow';
import { ResultsTable } from './ResultsTable';
import { ResultsMap } from './ResultsMap';
import { GeoPlaybackWidget } from '../Visualization/GeoPlaybackWidget';
import { detectGeoColumns } from '../../utils/geoDetect';
import type { GeoInfo } from '../../utils/geoDetect';
import { useFlowStore, serializeGraph } from '../../store/flowStore';
import { InterpretPanel } from './InterpretPanel';
import { streamInterpret } from '../../api/agent';
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

  // Interpretation state — local per-selection, resets on cube change
  const [interpretText, setInterpretText] = useState('');
  const [interpretLoading, setInterpretLoading] = useState(false);
  const [interpretOpen, setInterpretOpen] = useState(false);
  const [interpretError, setInterpretError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

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
  const workflowId = useFlowStore((s) => s.workflowId);

  // Derived
  const geoInfo: GeoInfo | null = useMemo(
    () => (results ? detectGeoColumns(results.rows) : null),
    [results]
  );

  const isOpen = selectedNodeId !== null && results !== null && results.rows.length > 0;

  // Reset row selection and interpretation state when selected cube changes
  useEffect(() => {
    setSelectedRowIndex(null);
    setInterpretText('');
    setInterpretLoading(false);
    setInterpretOpen(false);
    setInterpretError(null);
    abortControllerRef.current?.abort();
  }, [selectedNodeId]);

  const handleInterpret = useCallback(async () => {
    if (!selectedNodeId || !results) return;

    // Read expensive/unstable values from store snapshot (not selectors)
    const store = useFlowStore.getState();
    const allResults = store.results;
    const workflowGraph = serializeGraph(store.nodes, store.edges);
    const node = store.nodes.find((n) => n.id === selectedNodeId);
    const cubeCategory = node?.data.cubeDef.category ?? 'unknown';

    // Abort any in-progress interpretation
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    setInterpretText('');
    setInterpretError(null);
    setInterpretLoading(true);
    setInterpretOpen(true);

    try {
      for await (const event of streamInterpret(
        workflowId,
        workflowGraph as unknown as Record<string, unknown>,
        allResults as unknown as Record<string, unknown>,
        selectedNodeId,
        cubeName,
        cubeCategory,
      )) {
        if (abortControllerRef.current?.signal.aborted) break;
        if (event.type === 'text' && typeof event.data === 'string') {
          setInterpretText(prev => prev + event.data);
        }
        if (event.type === 'done') break;
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        setInterpretError('Interpretation failed — try again.');
      }
    } finally {
      setInterpretLoading(false);
    }
  }, [selectedNodeId, results, workflowId, cubeName]);

  const handleDiscuss = useCallback(() => {
    window.dispatchEvent(new CustomEvent('open-results-followup', {
      detail: {
        interpretationSummary: interpretText,
        persona: 'results_followup',
      },
    }));
  }, [interpretText]);

  return (
    <div className={`results-drawer${isOpen ? ' results-drawer--open' : ''}`} data-tour="results-drawer">
      {/* Handle / grip — click to close */}
      <div className="results-drawer__handle" onClick={() => setSelectedResultNodeId(null)}>
        <div className="results-drawer__grip" />
      </div>

      {/* Header */}
      <div className="results-drawer__header">
        <span className="results-drawer__title">{cubeName} Results</span>
        <div className="results-drawer__header-actions">
          {!interpretOpen && (
            <button
              className="results-drawer__interpret-trigger"
              onClick={handleInterpret}
              disabled={interpretLoading}
              aria-label="Interpret results with AI"
            >
              <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                <path d="M8 1L10 5.5L15 6.5L11.5 10L12.5 15L8 12.5L3.5 15L4.5 10L1 6.5L6 5.5L8 1Z" fill="currentColor" opacity="0.9"/>
              </svg>
              <span>Interpret</span>
            </button>
          )}
          <button
            className="results-drawer__close"
            onClick={() => setSelectedResultNodeId(null)}
          >
            <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Interpretation panel — inline between header and table */}
      {interpretOpen && results && (
        <InterpretPanel
          loading={interpretLoading}
          text={interpretText}
          error={interpretError}
          onDismiss={() => setInterpretOpen(false)}
          onDiscuss={handleDiscuss}
        />
      )}

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
