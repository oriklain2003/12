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

// ── Inline SVG illustrations ─────────────────────────────────────────────────

function TimeRangeIllustration() {
  return (
    <svg className="tour-tooltip__illustration" width="200" height="52" viewBox="0 0 200 52">
      <rect x="10" y="6" width="180" height="40" rx="10" fill="rgba(99, 102, 241, 0.08)" stroke="rgba(99, 102, 241, 0.25)" strokeWidth="1" />
      {/* clock icon */}
      <circle cx="40" cy="26" r="11" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
      <line x1="40" y1="26" x2="40" y2="18" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="40" y1="26" x2="46" y2="26" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeLinecap="round" />
      {/* sweeping second hand animation */}
      <line x1="40" y1="26" x2="40" y2="17" stroke="rgba(99, 102, 241, 0.6)" strokeWidth="1" strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 40 26" to="360 40 26" dur="4s" repeatCount="indefinite" />
      </line>
      {/* arrow pointing right */}
      <line x1="60" y1="26" x2="80" y2="26" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" strokeLinecap="round" />
      <polyline points="76,22 80,26 76,30" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* 90 days label */}
      <text x="130" y="30" textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize="15" fontWeight="600" fontFamily="DM Sans, system-ui">90 days</text>
    </svg>
  );
}

function ToggleAnomalyIllustration() {
  return (
    <svg className="tour-tooltip__illustration" width="180" height="48" viewBox="0 0 180 48">
      <rect x="10" y="6" width="160" height="36" rx="10" fill="rgba(99, 102, 241, 0.08)" stroke="rgba(99, 102, 241, 0.25)" strokeWidth="1" />
      {/* toggle track */}
      <rect x="28" y="15" width="36" height="18" rx="9" fill="rgba(34, 197, 94, 0.5)" />
      {/* toggle knob with slide animation */}
      <circle cx="46" cy="24" r="6" fill="#fff">
        <animate attributeName="cx" values="37;55;55" dur="1.5s" begin="0.3s" fill="freeze" />
      </circle>
      {/* track fill animation */}
      <rect x="28" y="15" width="36" height="18" rx="9" fill="rgba(34, 197, 94, 0.5)">
        <animate attributeName="fill" values="rgba(120,120,140,0.3);rgba(34, 197, 94, 0.5);rgba(34, 197, 94, 0.5)" dur="1.5s" begin="0.3s" fill="freeze" />
      </rect>
      {/* label */}
      <text x="80" y="22" fill="rgba(255,255,255,0.6)" fontSize="10" fontFamily="DM Sans, system-ui">is_anomaly</text>
      {/* checkmark appears */}
      <text x="80" y="34" fill="rgba(34, 197, 94, 0.8)" fontSize="11" fontWeight="500" fontFamily="DM Sans, system-ui">
        <tspan opacity="0">
          <animate attributeName="opacity" values="0;0;1" dur="1.5s" begin="0.3s" fill="freeze" />
          true
        </tspan>
      </text>
    </svg>
  );
}

function ConnectPipelineIllustration() {
  return (
    <svg className="tour-tooltip__illustration" width="320" height="70" viewBox="0 0 320 70">
      {/* All Flights cube */}
      <rect x="5" y="12" width="110" height="46" rx="10" fill="rgba(99, 102, 241, 0.12)" stroke="rgba(99, 102, 241, 0.35)" strokeWidth="1" />
      <text x="60" y="30" textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize="11" fontWeight="500" fontFamily="DM Sans, system-ui">All Flights</text>
      <text x="60" y="48" textAnchor="middle" fill="rgba(34, 197, 94, 0.7)" fontSize="9" fontFamily="DM Sans, system-ui">flight_ids</text>
      {/* source handle */}
      <circle cx="115" cy="44" r="5" fill="#22c55e" stroke="rgba(34, 197, 94, 0.3)" strokeWidth="2" />

      {/* animated connection line */}
      <line x1="120" y1="44" x2="200" y2="44" stroke="rgba(34, 197, 94, 0.35)" strokeWidth="2" strokeDasharray="6 4">
        <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="1.2s" repeatCount="indefinite" />
      </line>
      {/* flow arrow */}
      <polygon points="196,39 206,44 196,49" fill="rgba(34, 197, 94, 0.4)">
        <animate attributeName="opacity" values="0.3;0.7;0.3" dur="1.2s" repeatCount="indefinite" />
      </polygon>

      {/* target handle */}
      <circle cx="205" cy="44" r="5" fill="#22c55e" stroke="rgba(34, 197, 94, 0.3)" strokeWidth="2" />
      {/* Get Anomalies cube */}
      <rect x="205" y="12" width="110" height="46" rx="10" fill="rgba(99, 102, 241, 0.12)" stroke="rgba(99, 102, 241, 0.35)" strokeWidth="1" />
      <text x="260" y="30" textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize="11" fontWeight="500" fontFamily="DM Sans, system-ui">Get Anomalies</text>
      <text x="260" y="48" textAnchor="middle" fill="rgba(34, 197, 94, 0.7)" fontSize="9" fontFamily="DM Sans, system-ui">flight_ids</text>
    </svg>
  );
}

function ResultsTableIllustration() {
  return (
    <svg className="tour-tooltip__illustration" width="280" height="78" viewBox="0 0 280 78">
      <rect x="10" y="4" width="260" height="70" rx="10" fill="rgba(99, 102, 241, 0.06)" stroke="rgba(99, 102, 241, 0.2)" strokeWidth="1" />
      {/* header row */}
      <rect x="10" y="4" width="260" height="18" rx="10" fill="rgba(99, 102, 241, 0.1)" />
      <rect x="10" y="14" width="260" height="8" fill="rgba(99, 102, 241, 0.1)" />
      <text x="50" y="16" fill="rgba(255,255,255,0.5)" fontSize="8" fontWeight="500" fontFamily="DM Sans, system-ui">flight_id</text>
      <text x="120" y="16" fill="rgba(255,255,255,0.5)" fontSize="8" fontWeight="500" fontFamily="DM Sans, system-ui">callsign</text>
      <text x="190" y="16" fill="rgba(255,255,255,0.5)" fontSize="8" fontWeight="500" fontFamily="DM Sans, system-ui">severity</text>
      <text x="245" y="16" fill="rgba(255,255,255,0.5)" fontSize="8" fontWeight="500" fontFamily="DM Sans, system-ui">anomaly</text>
      {/* divider */}
      <line x1="10" y1="22" x2="270" y2="22" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      {/* row 1 */}
      <text x="50" y="35" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="DM Sans, system-ui">FL-28471</text>
      <text x="120" y="35" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="DM Sans, system-ui">UAL412</text>
      <text x="195" y="35" fill="rgba(251, 191, 36, 0.8)" fontSize="8" fontFamily="DM Sans, system-ui">0.87</text>
      <circle cx="255" cy="32" r="4" fill="rgba(34, 197, 94, 0.6)" />
      <line x1="10" y1="42" x2="270" y2="42" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      {/* row 2 */}
      <text x="50" y="55" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="DM Sans, system-ui">FL-91835</text>
      <text x="120" y="55" fill="rgba(255,255,255,0.4)" fontSize="8" fontFamily="DM Sans, system-ui">DAL201</text>
      <text x="195" y="55" fill="rgba(239, 68, 68, 0.8)" fontSize="8" fontFamily="DM Sans, system-ui">0.94</text>
      <circle cx="255" cy="52" r="4" fill="rgba(34, 197, 94, 0.6)" />
      <line x1="10" y1="62" x2="270" y2="62" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      {/* row 3 faded */}
      <text x="50" y="72" fill="rgba(255,255,255,0.2)" fontSize="8" fontFamily="DM Sans, system-ui">FL-44029</text>
      <text x="120" y="72" fill="rgba(255,255,255,0.2)" fontSize="8" fontFamily="DM Sans, system-ui">SWA789</text>
      <text x="195" y="72" fill="rgba(251, 191, 36, 0.5)" fontSize="8" fontFamily="DM Sans, system-ui">0.72</text>
      <circle cx="255" cy="69" r="4" fill="rgba(34, 197, 94, 0.3)" />
    </svg>
  );
}

function AgentPanelIllustration() {
  return (
    <svg className="tour-tooltip__illustration" width="260" height="100" viewBox="0 0 260 100">
      {/* Panel frame */}
      <rect x="10" y="4" width="240" height="92" rx="10" fill="rgba(99, 102, 241, 0.06)" stroke="rgba(99, 102, 241, 0.2)" strokeWidth="1" />
      {/* Header bar */}
      <rect x="10" y="4" width="240" height="22" rx="10" fill="rgba(99, 102, 241, 0.1)" />
      <rect x="10" y="16" width="240" height="10" fill="rgba(99, 102, 241, 0.1)" />
      <text x="24" y="18" fill="rgba(255,255,255,0.5)" fontSize="8" fontWeight="600" letterSpacing="0.5" fontFamily="DM Sans, system-ui">AGENT</text>
      {/* Mode toggle — three segments */}
      <rect x="70" y="9" width="120" height="14" rx="4" fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" />
      {/* Optimize segment */}
      <rect x="72" y="11" width="38" height="10" rx="3" fill="rgba(99, 102, 241, 0.18)" stroke="rgba(99, 102, 241, 0.25)" strokeWidth="0.5">
        <animate attributeName="fill" values="rgba(99,102,241,0.18);rgba(255,255,255,0.02);rgba(255,255,255,0.02)" dur="4s" begin="0s" repeatCount="indefinite" />
        <animate attributeName="stroke" values="rgba(99,102,241,0.25);rgba(255,255,255,0.06);rgba(255,255,255,0.06)" dur="4s" begin="0s" repeatCount="indefinite" />
      </rect>
      <text x="91" y="19" textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize="6" fontWeight="500" fontFamily="DM Sans, system-ui">
        <animate attributeName="fill" values="rgba(255,255,255,0.8);rgba(255,255,255,0.4);rgba(255,255,255,0.4)" dur="4s" begin="0s" repeatCount="indefinite" />
        Optimize
      </text>
      {/* Fix segment */}
      <rect x="112" y="11" width="26" height="10" rx="3" fill="rgba(255,255,255,0.02)">
        <animate attributeName="fill" values="rgba(255,255,255,0.02);rgba(239,68,68,0.15);rgba(255,255,255,0.02)" dur="4s" begin="0s" repeatCount="indefinite" />
      </rect>
      <text x="125" y="19" textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="6" fontWeight="500" fontFamily="DM Sans, system-ui">
        <animate attributeName="fill" values="rgba(255,255,255,0.4);rgba(255,255,255,0.8);rgba(255,255,255,0.4)" dur="4s" begin="0s" repeatCount="indefinite" />
        Fix
      </text>
      {/* General segment */}
      <rect x="140" y="11" width="48" height="10" rx="3" fill="rgba(255,255,255,0.02)">
        <animate attributeName="fill" values="rgba(255,255,255,0.02);rgba(255,255,255,0.02);rgba(99,102,241,0.18)" dur="4s" begin="0s" repeatCount="indefinite" />
      </rect>
      <text x="164" y="19" textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="6" fontWeight="500" fontFamily="DM Sans, system-ui">
        <animate attributeName="fill" values="rgba(255,255,255,0.4);rgba(255,255,255,0.4);rgba(255,255,255,0.8)" dur="4s" begin="0s" repeatCount="indefinite" />
        General
      </text>
      {/* Chat bubble — agent message */}
      <rect x="20" y="32" width="140" height="24" rx="6" fill="transparent" />
      <line x1="20" y1="32" x2="20" y2="56" stroke="rgba(99, 102, 241, 0.3)" strokeWidth="2" strokeLinecap="round" />
      <text x="28" y="43" fill="rgba(255,255,255,0.5)" fontSize="7" fontFamily="DM Sans, system-ui">I can optimize your pipeline</text>
      <text x="28" y="52" fill="rgba(255,255,255,0.35)" fontSize="7" fontFamily="DM Sans, system-ui">by reordering the filters...</text>
      {/* Chat bubble — user message */}
      <rect x="130" y="60" width="110" height="16" rx="6" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" />
      <text x="185" y="71" textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize="7" fontFamily="DM Sans, system-ui">Apply the changes</text>
      {/* Typing indicator dots */}
      <circle cx="26" cy="86" r="2" fill="rgba(99, 102, 241, 0.4)">
        <animate attributeName="opacity" values="0.3;1;0.3" dur="1.2s" begin="0s" repeatCount="indefinite" />
      </circle>
      <circle cx="34" cy="86" r="2" fill="rgba(99, 102, 241, 0.4)">
        <animate attributeName="opacity" values="0.3;1;0.3" dur="1.2s" begin="0.2s" repeatCount="indefinite" />
      </circle>
      <circle cx="42" cy="86" r="2" fill="rgba(99, 102, 241, 0.4)">
        <animate attributeName="opacity" values="0.3;1;0.3" dur="1.2s" begin="0.4s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}

const ILLUSTRATION_MAP: Record<string, () => React.JSX.Element> = {
  'time-range': TimeRangeIllustration,
  'toggle-anomaly': ToggleAnomalyIllustration,
  'connect-pipeline': ConnectPipelineIllustration,
  'results-table': ResultsTableIllustration,
  'agent-panel': AgentPanelIllustration,
};

// ── TourTooltip ──────────────────────────────────────────────────────────────

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
  const isCommandPaletteStep = stepIndex === 5;
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

  // Resolve illustration component
  const IllustrationComponent = step.illustration ? ILLUSTRATION_MAP[step.illustration] : null;

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

      {/* Illustration */}
      {IllustrationComponent && <IllustrationComponent />}

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
