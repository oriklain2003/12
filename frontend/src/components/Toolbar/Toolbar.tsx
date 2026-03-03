/**
 * Top toolbar for the workflow editor.
 *
 * Contains:
 *  - Dashboard link (placeholder nav)
 *  - Editable workflow name input
 *  - Save button (Phase 5 placeholder)
 *  - Run button (Phase 5 placeholder)
 */

import { useState } from 'react';
import './Toolbar.css';

export function Toolbar() {
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');

  const handleRun = () => {
    console.log('Run not yet implemented');
  };

  const handleSave = () => {
    console.log('Save not yet implemented');
  };

  return (
    <header className="toolbar glass">
      <div className="toolbar__left">
        <a href="/" className="toolbar__dashboard-link">
          Dashboard
        </a>
      </div>

      <div className="toolbar__center">
        <input
          type="text"
          className="toolbar__name-input nodrag"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
          aria-label="Workflow name"
          spellCheck={false}
        />
      </div>

      <div className="toolbar__actions">
        <button
          className="toolbar__btn toolbar__btn--save"
          onClick={handleSave}
        >
          Save
        </button>
        <button
          className="toolbar__btn toolbar__btn--run"
          onClick={handleRun}
        >
          Run
        </button>
      </div>
    </header>
  );
}
