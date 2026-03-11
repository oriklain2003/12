/**
 * Glass-morphism floating tooltip card for tour steps.
 * Positioned dynamically relative to the spotlight target,
 * with viewport clamping to prevent off-screen overflow.
 */

import { useEffect, useRef, useState } from 'react';
import type { TourStep } from './tourSteps';
import type { SpotlightRect } from './TourOverlay';

interface TourTooltipProps {
  step: TourStep;
  stepIndex: number;
  totalSteps: number;
  spotlight: SpotlightRect | null;
  onNext: () => void;
  onPrev: () => void;
  onSkip: () => void;
  isFirst: boolean;
  isLast: boolean;
}

const TOOLTIP_GAP = 16;
const TOOLTIP_WIDTH = 380;
const VIEWPORT_MARGIN = 16;

function computePosition(
  position: TourStep['position'],
  spotlight: SpotlightRect | null,
  tooltipHeight: number,
): React.CSSProperties {
  if (!spotlight || position === 'center') {
    return {
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
    };
  }

  const { x, y, width, height } = spotlight;
  const vh = window.innerHeight;
  const vw = window.innerWidth;

  switch (position) {
    case 'right': {
      // Clamp vertical center within viewport
      const idealTop = y + height / 2;
      const clampedTop = Math.max(VIEWPORT_MARGIN + tooltipHeight / 2, Math.min(vh - VIEWPORT_MARGIN - tooltipHeight / 2, idealTop));
      return {
        top: clampedTop,
        left: x + width + TOOLTIP_GAP,
        transform: 'translateY(-50%)',
        maxWidth: `calc(100vw - ${x + width + TOOLTIP_GAP + VIEWPORT_MARGIN}px)`,
      };
    }
    case 'left': {
      const idealTop = y + height / 2;
      const clampedTop = Math.max(VIEWPORT_MARGIN + tooltipHeight / 2, Math.min(vh - VIEWPORT_MARGIN - tooltipHeight / 2, idealTop));
      return {
        top: clampedTop,
        left: x - TOOLTIP_GAP,
        transform: 'translate(-100%, -50%)',
        maxWidth: x - TOOLTIP_GAP - VIEWPORT_MARGIN,
      };
    }
    case 'bottom': {
      const bottomSpace = vh - (y + height + TOOLTIP_GAP);
      const topSpace = y - TOOLTIP_GAP;

      // If target is huge (like the canvas), position inside it near the top
      if (height > vh * 0.5) {
        return {
          top: Math.max(y + TOOLTIP_GAP + 60, VIEWPORT_MARGIN),
          left: Math.max(VIEWPORT_MARGIN, Math.min(vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN, x + width / 2 - TOOLTIP_WIDTH / 2)),
        };
      }

      // If not enough space below, try above
      if (bottomSpace < tooltipHeight + VIEWPORT_MARGIN && topSpace > bottomSpace) {
        return {
          top: Math.max(y - TOOLTIP_GAP, VIEWPORT_MARGIN + tooltipHeight),
          left: Math.max(VIEWPORT_MARGIN, Math.min(vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN, x + width / 2 - TOOLTIP_WIDTH / 2)),
          transform: 'translateY(-100%)',
        };
      }

      return {
        top: y + height + TOOLTIP_GAP,
        left: Math.max(VIEWPORT_MARGIN, Math.min(vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN, x + width / 2 - TOOLTIP_WIDTH / 2)),
      };
    }
    case 'top': {
      return {
        top: y - TOOLTIP_GAP,
        left: Math.max(VIEWPORT_MARGIN, Math.min(vw - TOOLTIP_WIDTH - VIEWPORT_MARGIN, x + width / 2 - TOOLTIP_WIDTH / 2)),
        transform: 'translateY(-100%)',
      };
    }
    default:
      return {
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
      };
  }
}

export function TourTooltip({
  step,
  stepIndex,
  totalSteps,
  spotlight,
  onNext,
  onPrev,
  onSkip,
  isFirst,
  isLast,
}: TourTooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipHeight, setTooltipHeight] = useState(200);

  // Measure actual tooltip height after render for accurate positioning
  useEffect(() => {
    if (tooltipRef.current) {
      setTooltipHeight(tooltipRef.current.offsetHeight);
    }
  }, [stepIndex]);

  const tooltipWidth = step.hero ? 440 : TOOLTIP_WIDTH;

  // For the command palette step, offset to the right so the palette doesn't cover it
  const isCommandPaletteStep = stepIndex === 6;
  let style: React.CSSProperties;
  if (isCommandPaletteStep) {
    style = {
      top: '20%',
      right: VIEWPORT_MARGIN + 40,
      left: 'auto',
      transform: 'none',
    };
  } else {
    style = computePosition(step.position, spotlight, tooltipHeight);
  }

  return (
    <div
      ref={tooltipRef}
      className={`tour-tooltip ${step.hero ? 'tour-tooltip--hero' : ''}`}
      style={{ ...style, width: tooltipWidth }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Step counter */}
      {!step.hero && (
        <div className="tour-tooltip__step-label">
          Step {stepIndex + 1} of {totalSteps}
        </div>
      )}

      <h3 className={`tour-tooltip__title ${step.hero ? 'tour-tooltip__title--hero' : ''}`}>
        {step.title}
      </h3>

      <p className="tour-tooltip__description">
        {step.description}
      </p>

      {/* Connection illustration for step 4 */}
      {stepIndex === 4 && (
        <svg className="tour-tooltip__connection-illustration" width="240" height="60" viewBox="0 0 240 60">
          <rect x="10" y="15" width="70" height="30" rx="8" fill="rgba(99, 102, 241, 0.15)" stroke="rgba(99, 102, 241, 0.4)" strokeWidth="1" />
          <text x="45" y="34" textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="10" fontFamily="DM Sans">Source</text>
          <circle cx="80" cy="30" r="4" fill="#6366f1" />

          <line x1="84" y1="30" x2="156" y2="30" stroke="rgba(99, 102, 241, 0.4)" strokeWidth="1.5" strokeDasharray="4 3">
            <animate attributeName="stroke-dashoffset" from="0" to="-14" dur="1s" repeatCount="indefinite" />
          </line>

          <rect x="160" y="15" width="70" height="30" rx="8" fill="rgba(99, 102, 241, 0.15)" stroke="rgba(99, 102, 241, 0.4)" strokeWidth="1" />
          <text x="195" y="34" textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize="10" fontFamily="DM Sans">Target</text>
          <circle cx="160" cy="30" r="4" fill="#3b82f6" />
        </svg>
      )}

      {/* Navigation */}
      <div className="tour-tooltip__nav">
        {isFirst ? (
          <>
            <button className="glass-btn tour-tooltip__btn" onClick={onSkip}>
              Skip
            </button>
            <button className="glass-btn glass-btn--accent tour-tooltip__btn" onClick={onNext}>
              Show Me Around
            </button>
          </>
        ) : isLast ? (
          <button className="glass-btn glass-btn--accent tour-tooltip__btn" onClick={onNext}>
            Get Started
          </button>
        ) : (
          <>
            <button className="glass-btn tour-tooltip__btn" onClick={onSkip}>
              Skip
            </button>
            <div className="tour-tooltip__nav-group">
              <button
                className="glass-btn tour-tooltip__btn"
                onClick={onPrev}
                disabled={stepIndex === 0}
              >
                Back
              </button>
              <button className="glass-btn glass-btn--accent tour-tooltip__btn" onClick={onNext}>
                Next
              </button>
            </div>
          </>
        )}
      </div>

      {/* Step dots */}
      <div className="tour-tooltip__dots">
        {Array.from({ length: totalSteps }).map((_, i) => (
          <span
            key={i}
            className={`tour-tooltip__dot ${i === stepIndex ? 'tour-tooltip__dot--active' : ''} ${i < stepIndex ? 'tour-tooltip__dot--done' : ''}`}
          />
        ))}
      </div>
    </div>
  );
}
