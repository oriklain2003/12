/**
 * OptionCards — inline option card block rendered from present_options tool result.
 * Supports single-select and multi-select modes with free-text fallback.
 */

import { useState } from 'react';
import type { WizardOptionsData } from '../../types/wizard';
import './OptionCards.css';

interface OptionCardsProps {
  data: WizardOptionsData;
  onSelect: (selection: string) => void;
  disabled?: boolean;
}

export function OptionCards({ data, onSelect, disabled }: OptionCardsProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState(false);
  const [freeText, setFreeText] = useState('');

  const isLocked = submitted || disabled;

  function handleCardClick(optionId: string, optionTitle: string) {
    if (isLocked) return;

    if (!data.multi_select) {
      // Single-select: immediately send selection
      setSelectedIds(new Set([optionId]));
      setSubmitted(true);
      onSelect(`I selected: ${optionTitle}`);
    } else {
      // Multi-select: toggle card
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (next.has(optionId)) {
          next.delete(optionId);
        } else {
          next.add(optionId);
        }
        return next;
      });
    }
  }

  function handleConfirmMultiSelect() {
    if (isLocked || selectedIds.size === 0) return;
    const selectedTitles = data.options
      .filter((opt) => selectedIds.has(opt.id))
      .map((opt) => opt.title)
      .join(', ');
    setSubmitted(true);
    onSelect(`I selected: ${selectedTitles}`);
  }

  function handleFreeTextSend() {
    const trimmed = freeText.trim();
    if (!trimmed || isLocked) return;
    setSubmitted(true);
    onSelect(trimmed);
  }

  function handleFreeTextKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleFreeTextSend();
    }
  }

  const hasOptions = data.options.length > 0;

  return (
    <div className={`option-cards${isLocked ? ' option-cards--disabled' : ''}`}>
      {data.question && (
        <div className="option-cards__question">{data.question}</div>
      )}

      {hasOptions ? (
        <div className="option-cards__list">
          {data.options.map((option) => {
            const isSelected = selectedIds.has(option.id);
            return (
              <button
                key={option.id}
                className={`option-card${isSelected ? ' option-card--selected' : ''}`}
                onClick={() => handleCardClick(option.id, option.title)}
                disabled={isLocked}
                type="button"
              >
                <div className="option-card__title">{option.title}</div>
                {option.description && (
                  <div className="option-card__description">{option.description}</div>
                )}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="option-cards__empty">
          No options available — type your answer below.
        </div>
      )}

      {data.multi_select && selectedIds.size > 0 && !isLocked && (
        <button
          className="glass-btn option-cards__confirm"
          onClick={handleConfirmMultiSelect}
          type="button"
          style={{ fontSize: 14, fontWeight: 600, padding: '10px 20px' }}
        >
          Confirm selection
        </button>
      )}

      <div className="option-cards__free-text">
        <input
          className="option-cards__free-text-input"
          type="text"
          placeholder="Or type your own..."
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          onKeyDown={handleFreeTextKeyDown}
          disabled={isLocked}
          aria-label="Free text answer"
        />
        <button
          className="glass-btn option-cards__free-text-btn"
          onClick={handleFreeTextSend}
          disabled={!freeText.trim() || isLocked}
          type="button"
          aria-label="Send message"
          style={{ fontSize: 14, fontWeight: 600, padding: '10px 20px' }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
