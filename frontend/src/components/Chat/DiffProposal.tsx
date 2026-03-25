/**
 * DiffProposal — structured diff block with Apply Changes and Reject Changes buttons.
 * Shows add/remove/update operations proposed by the Canvas Agent.
 * On Apply: calls applyAgentDiff from the store and shows toast confirmation.
 * On Reject: removes the proposal from the message thread.
 */

import { useState } from 'react';
import { toast } from 'sonner';
import type { AgentDiff } from '../../types/agent';
import { useFlowStore } from '../../store/flowStore';
import './ChatPanel.css';

interface DiffProposalProps {
  diff: AgentDiff;
}

/** Format a param value for display */
function formatValue(v: unknown): string {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'string') return `"${v}"`;
  if (typeof v === 'boolean' || typeof v === 'number') return String(v);
  if (Array.isArray(v)) return `[${v.map(formatValue).join(', ')}]`;
  return JSON.stringify(v);
}

/** Get a node label from the current canvas by ID */
function getNodeLabel(nodeId: string): string {
  const node = useFlowStore.getState().nodes.find((n) => n.id === nodeId);
  if (!node) return nodeId;
  return node.data.cubeDef?.display_name ?? node.data.cube_id ?? nodeId;
}

/** Get current param value from a node */
function getCurrentValue(nodeId: string, paramName: string): unknown | undefined {
  const node = useFlowStore.getState().nodes.find((n) => n.id === nodeId);
  if (!node?.data?.params) return undefined;
  return (node.data.params as Record<string, unknown>)[paramName];
}

/** Resolve an edge ID to a human-readable "SourceNode.output → TargetNode.input" label */
function getEdgeLabel(edgeId: string): { source: string; sourceHandle: string; target: string; targetHandle: string } | null {
  const edge = useFlowStore.getState().edges.find((e) => e.id === edgeId);
  if (!edge) return null;
  return {
    source: getNodeLabel(edge.source),
    sourceHandle: edge.sourceHandle ?? '',
    target: getNodeLabel(edge.target),
    targetHandle: edge.targetHandle ?? '',
  };
}

export function DiffProposal({ diff }: DiffProposalProps) {
  const [applied, setApplied] = useState(false);
  const [rejected, setRejected] = useState(false);

  if (rejected) return null;

  const handleApply = () => {
    useFlowStore.getState().applyAgentDiff(diff);
    setApplied(true);
    toast.success('Changes applied to canvas');
  };

  const handleReject = () => {
    useFlowStore.getState().setPendingDiff(null);
    setRejected(true);
  };

  return (
    <div className="diff-proposal">
      <div className="diff-proposal__header">
        <span className="diff-proposal__title">Proposed Changes</span>
      </div>

      <div className="diff-proposal__items">
        {(diff.add_nodes ?? []).map((node, i) => (
          <div key={`add-node-${i}`} className="diff-proposal__item diff-proposal__item--block">
            <div className="diff-proposal__item-row">
              <span className="diff-proposal__badge diff-proposal__badge--add">+</span>
              <span className="diff-proposal__item-text">
                Add <code className="diff-proposal__item-mono">{node.label ?? node.cube_id}</code> cube
              </span>
            </div>
            {node.params && Object.keys(node.params).length > 0 && (
              <div className="diff-proposal__detail-list">
                {Object.entries(node.params).map(([k, v]) => (
                  <div key={k} className="diff-proposal__detail">
                    <span className="diff-proposal__detail-key">{k}</span>
                    <span className="diff-proposal__detail-arrow">→</span>
                    <span className="diff-proposal__detail-new">{formatValue(v)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {(diff.remove_node_ids ?? []).map((id) => (
          <div key={`remove-node-${id}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--remove">−</span>
            <span className="diff-proposal__item-text">
              Remove <code className="diff-proposal__item-mono">{getNodeLabel(id)}</code>
            </span>
          </div>
        ))}

        {(diff.update_params ?? []).map((update, i) => (
          <div key={`update-params-${i}`} className="diff-proposal__item diff-proposal__item--block">
            <div className="diff-proposal__item-row">
              <span className="diff-proposal__badge diff-proposal__badge--update">~</span>
              <span className="diff-proposal__item-text">
                Update <code className="diff-proposal__item-mono">{getNodeLabel(update.node_id)}</code>
              </span>
            </div>
            <div className="diff-proposal__detail-list">
              {Object.entries(update.params).map(([k, v]) => {
                const current = getCurrentValue(update.node_id, k);
                return (
                  <div key={k} className="diff-proposal__detail">
                    <span className="diff-proposal__detail-key">{k}</span>
                    {current !== undefined && (
                      <>
                        <span className="diff-proposal__detail-old">{formatValue(current)}</span>
                        <span className="diff-proposal__detail-arrow">→</span>
                      </>
                    )}
                    {current === undefined && (
                      <span className="diff-proposal__detail-arrow">→</span>
                    )}
                    <span className="diff-proposal__detail-new">{formatValue(v)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {(diff.add_edges ?? []).map((edge, i) => (
          <div key={`add-edge-${i}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--add">+</span>
            <span className="diff-proposal__item-text">
              Connect{' '}
              <code className="diff-proposal__item-mono">{getNodeLabel(edge.source)}</code>
              {edge.source_handle && (
                <span className="diff-proposal__handle-label">.{edge.source_handle}</span>
              )}
              {' '}→{' '}
              <code className="diff-proposal__item-mono">{getNodeLabel(edge.target)}</code>
              {edge.target_handle && (
                <span className="diff-proposal__handle-label">.{edge.target_handle}</span>
              )}
            </span>
          </div>
        ))}

        {(diff.remove_edge_ids ?? []).map((id) => {
          const info = getEdgeLabel(id);
          return (
            <div key={`remove-edge-${id}`} className="diff-proposal__item">
              <span className="diff-proposal__badge diff-proposal__badge--remove">−</span>
              <span className="diff-proposal__item-text">
                {info ? (
                  <>
                    Disconnect{' '}
                    <code className="diff-proposal__item-mono">{info.source}</code>
                    {info.sourceHandle && (
                      <span className="diff-proposal__handle-label">.{info.sourceHandle}</span>
                    )}
                    {' '}→{' '}
                    <code className="diff-proposal__item-mono">{info.target}</code>
                    {info.targetHandle && (
                      <span className="diff-proposal__handle-label">.{info.targetHandle}</span>
                    )}
                  </>
                ) : (
                  <>Remove connection <code className="diff-proposal__item-mono">{id}</code></>
                )}
              </span>
            </div>
          );
        })}
      </div>

      <div className="diff-proposal__footer">
        {applied ? (
          <span className="diff-proposal__applied">Applied</span>
        ) : (
          <>
            <button
              className="glass-btn"
              onClick={handleReject}
              style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
            >
              Reject
            </button>
            <button
              className="glass-btn glass-btn--accent"
              onClick={handleApply}
              style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
            >
              Apply
            </button>
          </>
        )}
      </div>
    </div>
  );
}
