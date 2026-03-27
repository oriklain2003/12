import { useMemo } from 'react';
import { renderMarkdown } from '../../utils/renderMarkdown';
import './InterpretPanel.css';

interface InterpretPanelProps {
  loading: boolean;
  text: string;
  error: string | null;
  onDismiss: () => void;
  onDiscuss: () => void;
}

export function InterpretPanel({ loading, text, error, onDismiss, onDiscuss }: InterpretPanelProps) {
  const rendered = useMemo(() => (text ? renderMarkdown(text) : null), [text]);

  return (
    <div className="interpret-panel">
      <div className="interpret-panel__header">
        <span className="interpret-panel__title">AI Interpretation</span>
        <button className="interpret-panel__dismiss" onClick={onDismiss}>Dismiss</button>
      </div>
      <div className={`interpret-panel__body${loading ? ' interpret-panel__body--streaming' : ''}`}>
        {error && <p className="interpret-panel__error">{error}</p>}
        {rendered && <div className="interpret-panel__text">{rendered}</div>}
        {loading && !text && <div className="interpret-panel__loading">Interpreting results...</div>}
      </div>
      {text && !loading && (
        <div className="interpret-panel__footer">
          <button className="interpret-panel__discuss" onClick={onDiscuss}>
            Discuss Results
          </button>
        </div>
      )}
    </div>
  );
}
