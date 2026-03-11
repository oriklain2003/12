/**
 * Custom React Flow node component for a Cube.
 * Renders the cube header, input params (with handles + editors),
 * output params (with handles), Full Result handle, and results preview.
 *
 * Execution status indicators:
 *  - Header badge: gray (pending), blue spinner (running), green check (done), red X (error), dash (skipped)
 *  - Error banner: floats ABOVE the node content (absolute positioned, bottom: calc(100% + 6px))
 *  - Running glow: subtle box-shadow when the node is actively running
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import { CubeCategory, ParamType } from '../../types/cube';
import type { CubeFlowNode } from '../../store/flowStore';
import { useFlowStore } from '../../store/flowStore';
import { PARAM_COLORS } from './ParamHandle';
import { ParamHandle } from './ParamHandle';
import { ParamField } from './ParamField';
import { ResultsPanel } from './ResultsPanel';
import './CubeNode.css';

// ─── Category color accent map ────────────────────────────────────────────────

const CATEGORY_COLORS: Record<CubeCategory, string> = {
  [CubeCategory.DATA_SOURCE]: '#6366f1', // indigo
  [CubeCategory.FILTER]: '#f59e0b',      // amber
  [CubeCategory.ANALYSIS]: '#8b5cf6',    // violet
  [CubeCategory.AGGREGATION]: '#06b6d4', // cyan
  [CubeCategory.OUTPUT]: '#10b981',      // emerald
};

// ─── Error banner with copy button ───────────────────────────────────────────

function ErrorBanner({ error }: { error: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(error).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [error]);

  return (
    <div className="cube-node__error-banner">
      <span className="cube-node__error-text">{error}</span>
      <button
        className="cube-node__error-copy nodrag"
        onClick={handleCopy}
        title="Copy error"
      >
        {copied ? (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.2" />
            <path d="M8 4V2a1 1 0 00-1-1H2a1 1 0 00-1 1v5a1 1 0 001 1h2" stroke="currentColor" strokeWidth="1.2" />
          </svg>
        )}
      </button>
    </div>
  );
}

// ─── Info Popover ─────────────────────────────────────────────────────────────

function CubeInfoPopover({ description, buttonRect, onClose }: {
  description: string;
  buttonRect: DOMRect;
  onClose: () => void;
}) {
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handlePointerDown(e: PointerEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('pointerdown', handlePointerDown, true);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  // Position below the button, clamped to viewport
  const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 320);
  const left = Math.max(8, Math.min(buttonRect.left, window.innerWidth - 268));

  return createPortal(
    <div
      ref={popoverRef}
      className="cube-info-popover"
      style={{ top, left }}
    >
      <p className="cube-info-popover__text">{description}</p>
    </div>,
    document.body
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export function CubeNode({ id, data, selected, isConnectable }: NodeProps<CubeFlowNode>) {
  const { cubeDef } = data;
  const categoryColor = CATEGORY_COLORS[cubeDef.category] ?? '#6b7280';
  const removeNode = useFlowStore((s) => s.removeNode);

  // Recalculate handle positions when connections change (row height may shift)
  const updateNodeInternals = useUpdateNodeInternals();
  const connectedHandles = useFlowStore(
    (s) => s.edges.filter((e) => e.source === id || e.target === id).map((e) => e.id).join(',')
  );
  useEffect(() => {
    updateNodeInternals(id);
  }, [connectedHandles, id, updateNodeInternals]);
  const [showInfo, setShowInfo] = useState(false);
  const infoButtonRef = useRef<HTMLButtonElement>(null);

  // Execution state from store — per-node status
  const executionStatus = useFlowStore((s) => s.executionStatus[id]);
  const isRunning = useFlowStore((s) => s.isRunning);

  // Results drawer — open drawer when header clicked and results exist
  const setSelectedResultNodeId = useFlowStore((s) => s.setSelectedResultNodeId);
  const hasResults = useFlowStore((s) => !!s.results[id]);

  // Node entrance animation
  const clearNodeNew = useFlowStore((s) => s.clearNodeNew);

  // Build class list for the root node div
  const nodeClasses = [
    'cube-node',
    'glass--node',
    selected ? 'cube-node--selected' : '',
    executionStatus?.status === 'running' ? 'cube-node--running' : '',
    data.isNew ? 'cube-node--entering' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={nodeClasses}
      onAnimationEnd={() => { if (data.isNew) clearNodeNew(id); }}
    >
      {/* Error banner — absolute positioned ABOVE the node (bottom: calc(100% + 6px)) */}
      {executionStatus?.status === 'error' && executionStatus.error && (
        <ErrorBanner error={executionStatus.error} />
      )}

      {/* Close button — hidden during execution to prevent accidental removal */}
      {!isRunning && (
        <button
          className="cube-node__close nodrag"
          onClick={() => removeNode(id)}
          aria-label="Remove node"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      )}

      {/* Info button — shows cube description popover */}
      {cubeDef.description && (
        <button
          ref={infoButtonRef}
          className={`cube-node__info nodrag nopan${showInfo ? ' cube-node__info--active' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            setShowInfo((prev) => !prev);
          }}
          aria-label="Cube info"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.2" />
            <path d="M7 6.5V10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            <circle cx="7" cy="4.5" r="0.75" fill="currentColor" />
          </svg>
        </button>
      )}

      {/* Info popover */}
      {showInfo && cubeDef.description && infoButtonRef.current && (
        <CubeInfoPopover
          description={cubeDef.description}
          buttonRect={infoButtonRef.current.getBoundingClientRect()}
          onClose={() => setShowInfo(false)}
        />
      )}

      {/* Header — click to open results drawer (only when results exist) */}
      <div
        className="cube-node__header"
        onClick={hasResults ? () => setSelectedResultNodeId(id) : undefined}
        style={{ cursor: hasResults ? 'pointer' : 'default' }}
      >
        <span className="cube-node__category-dot" style={{ background: categoryColor }} />
        <span className="cube-node__header-name">{cubeDef.name}</span>

        {/* Execution timing + status indicator */}
        {executionStatus && (
          <>
            {executionStatus.execution_ms != null && (
              <span className="cube-node__timing">
                {executionStatus.execution_ms < 1000
                  ? `${executionStatus.execution_ms}ms`
                  : `${(executionStatus.execution_ms / 1000).toFixed(1)}s`}
              </span>
            )}
            <span className={`cube-node__status cube-node__status--${executionStatus.status}`}>
              {executionStatus.status === 'running' && (
                <span className="cube-node__spinner" />
              )}
              {executionStatus.status === 'done' && (
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {executionStatus.status === 'error' && (
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              )}
              {executionStatus.status === 'skipped' && (
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              )}
            </span>
          </>
        )}
      </div>

      <div className="cube-node__body">
        {/* Input params */}
        {cubeDef.inputs.length > 0 && (
          <>
            <div className="cube-node__section-label">Inputs</div>
            {cubeDef.inputs.map((param) => (
              <div key={param.name} className="cube-node__param-row cube-node__param-row--input">
                <ParamHandle param={param} type="target" isConnectable={isConnectable} />
                <div className="cube-node__param-content">
                  <span className="cube-node__param-label">{param.name}</span>
                  <ParamField nodeId={id} param={param} />
                </div>
              </div>
            ))}
          </>
        )}

        {/* Output params */}
        {cubeDef.outputs.length > 0 && (
          <>
            <div className="cube-node__section-label">Outputs</div>
            {cubeDef.outputs.map((param) => {
              // Skip the __full_result__ param — rendered separately below
              if (param.name === '__full_result__') return null;
              return (
                <div key={param.name} className="cube-node__param-row cube-node__param-row--output">
                  <ParamHandle param={param} type="source" isConnectable={isConnectable} />
                  <span className="cube-node__param-label">{param.name}</span>
                </div>
              );
            })}
          </>
        )}

        {/* Full Result handle — always present */}
        <div className="cube-node__full-result-row">
          <span className="cube-node__full-result-label">Full Result</span>
          <Handle
            type="source"
            position={Position.Right}
            id="__full_result__"
            isConnectable={isConnectable}
            className="nodrag cube-node__handle"
            style={{
              background: PARAM_COLORS[ParamType.JSON_OBJECT],
              width: 12,
              height: 12,
              borderRadius: 4,
              border: '2px solid rgba(0,0,0,0.3)',
            }}
          />
        </div>

        {/* Results preview */}
        <ResultsPanel nodeId={id} />
      </div>
    </div>
  );
}
