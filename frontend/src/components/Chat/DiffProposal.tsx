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
          <div key={`add-node-${i}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--add">+</span>
            <span className="diff-proposal__item-text">
              Add{' '}
              <code className="diff-proposal__item-mono">{node.cube_id}</code>{' '}
              cube
            </span>
          </div>
        ))}

        {(diff.remove_node_ids ?? []).map((id) => (
          <div key={`remove-node-${id}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--remove">−</span>
            <span className="diff-proposal__item-text">
              Remove node{' '}
              <code className="diff-proposal__item-mono">{id}</code>
            </span>
          </div>
        ))}

        {(diff.update_params ?? []).map((update, i) => (
          <div key={`update-params-${i}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--update">~</span>
            <span className="diff-proposal__item-text">
              Update params on node{' '}
              <code className="diff-proposal__item-mono">{update.node_id}</code>
              {Object.keys(update.params).length > 0 && (
                <>
                  {' '}({Object.keys(update.params).map((k, ki) => (
                    <span key={k}>
                      <code className="diff-proposal__item-mono">{k}</code>
                      {ki < Object.keys(update.params).length - 1 ? ', ' : ''}
                    </span>
                  ))})
                </>
              )}
            </span>
          </div>
        ))}

        {(diff.add_edges ?? []).map((edge, i) => (
          <div key={`add-edge-${i}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--add">+</span>
            <span className="diff-proposal__item-text">
              Connect{' '}
              <code className="diff-proposal__item-mono">{edge.source}</code>
              {' '}→{' '}
              <code className="diff-proposal__item-mono">{edge.target}</code>
            </span>
          </div>
        ))}

        {(diff.remove_edge_ids ?? []).map((id) => (
          <div key={`remove-edge-${id}`} className="diff-proposal__item">
            <span className="diff-proposal__badge diff-proposal__badge--remove">−</span>
            <span className="diff-proposal__item-text">
              Remove connection{' '}
              <code className="diff-proposal__item-mono">{id}</code>
            </span>
          </div>
        ))}
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
              Reject Changes
            </button>
            <button
              className="glass-btn glass-btn--accent"
              onClick={handleApply}
              style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px' }}
            >
              Apply Changes
            </button>
          </>
        )}
      </div>
    </div>
  );
}
