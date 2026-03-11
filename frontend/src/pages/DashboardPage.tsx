import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import { getWorkflows, deleteWorkflow, updateWorkflow } from '../api/workflows';
import type { WorkflowResponse } from '../types/workflow';
import { Skeleton } from '../components/ui/Skeleton';
import { useThemeStore } from '../store/themeStore';
import './DashboardPage.css';

export function DashboardPage() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.title = 'ONYX 12';
    useThemeStore.getState().applyTheme();
  }, []);

  useEffect(() => {
    getWorkflows()
      .then((data) => {
        setWorkflows(data);
      })
      .catch(() => {
        toast.error('Failed to load workflows');
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
    }
  }, [renamingId]);

  function handleCardClick(id: string) {
    navigate(`/workflow/${id}`);
  }

  function handleRenameStart(wf: WorkflowResponse, e: React.MouseEvent) {
    e.stopPropagation();
    setRenamingId(wf.id);
    setRenameValue(wf.name);
  }

  async function handleRenameCommit(wf: WorkflowResponse) {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === wf.name) {
      setRenamingId(null);
      return;
    }
    try {
      const updated = await updateWorkflow(wf.id, trimmed, wf.graph_json);
      setWorkflows((prev) => prev.map((w) => (w.id === wf.id ? updated : w)));
    } catch {
      toast.error('Failed to rename workflow');
    }
    setRenamingId(null);
  }

  function handleRenameKeyDown(e: React.KeyboardEvent, wf: WorkflowResponse) {
    if (e.key === 'Enter') {
      void handleRenameCommit(wf);
    } else if (e.key === 'Escape') {
      setRenamingId(null);
    }
  }

  function handleDeleteStart(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    setDeletingId(id);
  }

  async function handleDeleteConfirm(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await deleteWorkflow(id);
      setWorkflows((prev) => prev.filter((w) => w.id !== id));
      toast.success('Workflow deleted');
    } catch {
      toast.error('Failed to delete workflow');
    }
    setDeletingId(null);
  }

  function handleDeleteCancel(e: React.MouseEvent) {
    e.stopPropagation();
    setDeletingId(null);
  }

  return (
    <div className="dashboard">
      <Toaster position="bottom-right" theme="dark" />

      <div className="dashboard__brand">
        <img src="/onyx-logo.svg" alt="ONYX" className="dashboard__brand-logo" />
        <span className="dashboard__brand-divider" />
        <span className="dashboard__brand-product">12</span>
      </div>

      <div className="dashboard__header">
        <h1 className="dashboard__title">Workflows</h1>
        <button
          className="dashboard__new-btn"
          onClick={() => navigate('/workflow/new')}
        >
          New Workflow
        </button>
      </div>

      {loading && (
        <div className="dashboard__grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="dashboard__card glass">
              <Skeleton height={18} width="60%" />
              <Skeleton height={12} width="45%" />
              <Skeleton height={12} width="40%" />
            </div>
          ))}
        </div>
      )}

      {!loading && workflows.length === 0 && (
        <div className="dashboard__empty">
          <p>No saved workflows</p>
          <button
            className="dashboard__new-btn"
            onClick={() => navigate('/workflow/new')}
            style={{ marginTop: '16px' }}
          >
            Create New Workflow
          </button>
        </div>
      )}

      {!loading && workflows.length > 0 && (
        <div className="dashboard__grid">
          {workflows.map((wf) => (
            <div
              key={wf.id}
              className="dashboard__card glass"
              onClick={() => handleCardClick(wf.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') handleCardClick(wf.id);
              }}
            >
              <div className="dashboard__card-name">
                {renamingId === wf.id ? (
                  <input
                    ref={renameInputRef}
                    className="dashboard__rename-input"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => void handleRenameCommit(wf)}
                    onKeyDown={(e) => handleRenameKeyDown(e, wf)}
                    onClick={(e) => e.stopPropagation()}
                  />
                ) : (
                  wf.name
                )}
              </div>

              <div className="dashboard__card-date">
                Created: {new Date(wf.created_at).toLocaleDateString()}
              </div>
              <div className="dashboard__card-date">
                Updated: {new Date(wf.updated_at).toLocaleDateString()}
              </div>

              {deletingId === wf.id ? (
                <div className="dashboard__delete-confirm" onClick={(e) => e.stopPropagation()}>
                  <span>Delete this workflow?</span>
                  <button
                    className="dashboard__card-action-btn dashboard__card-action-btn--danger"
                    onClick={(e) => void handleDeleteConfirm(wf.id, e)}
                  >
                    Confirm
                  </button>
                  <button
                    className="dashboard__card-action-btn"
                    onClick={handleDeleteCancel}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="dashboard__card-actions">
                  <button
                    className="dashboard__card-action-btn"
                    onClick={(e) => handleRenameStart(wf, e)}
                  >
                    Rename
                  </button>
                  <button
                    className="dashboard__card-action-btn dashboard__card-action-btn--danger"
                    onClick={(e) => handleDeleteStart(wf.id, e)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
