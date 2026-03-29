import { useMemo, useRef, useEffect } from 'react';
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
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom while streaming
  useEffect(() => {
    if (loading && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [text, loading]);

  const isDone = text && !loading;

  return (
    <div className={`interp${isDone ? ' interp--done' : ''}${loading ? ' interp--streaming' : ''}`}>
      {/* Ambient glow line */}
      <div className="interp__glow" />

      {/* Left accent rail */}
      <div className="interp__rail" />

      <div className="interp__inner">
        {/* Compact label row */}
        <div className="interp__label-row">
          <div className="interp__label">
            {loading && (
              <span className="interp__pulse-ring" />
            )}
            <svg className="interp__icon" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L10 5.5L15 6.5L11.5 10L12.5 15L8 12.5L3.5 15L4.5 10L1 6.5L6 5.5L8 1Z" fill="currentColor" opacity="0.9"/>
            </svg>
            <span className="interp__label-text">
              {loading ? 'Interpreting' : 'Interpretation'}
            </span>
            {loading && <span className="interp__dots"><span /><span /><span /></span>}
          </div>
          <button className="interp__close" onClick={onDismiss} aria-label="Dismiss interpretation">
            <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="interp__body" ref={scrollRef}>
          {error && <p className="interp__error">{error}</p>}
          {rendered && <div className="interp__text">{rendered}</div>}
          {loading && !text && (
            <div className="interp__skeleton">
              <div className="interp__skeleton-line" style={{ width: '85%' }} />
              <div className="interp__skeleton-line" style={{ width: '70%' }} />
              <div className="interp__skeleton-line" style={{ width: '55%' }} />
            </div>
          )}
        </div>

        {/* Action row — visible once streaming completes */}
        {isDone && (
          <div className="interp__actions">
            <button className="interp__action interp__action--discuss" onClick={onDiscuss}>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M2 2h12v8H5l-3 3V2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
              </svg>
              Discuss
            </button>
            <button className="interp__action interp__action--dismiss" onClick={onDismiss}>
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
