/**
 * Welcome Tour orchestrator.
 * Manages step state machine, keyboard nav, and portal rendering.
 * Auto-launches on first visit after 800ms delay.
 *
 * Interactive steps (drag & ⌘K) let pointer events pass through the
 * spotlight hole and auto-advance when the user adds a cube to the canvas.
 */

import { useEffect, useCallback, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTourStore } from './useTourStore';
import { TOUR_STEPS } from './tourSteps';
import { TourOverlay, getTargetRect, type SpotlightRect } from './TourOverlay';
import { TourTooltip } from './TourTooltip';
import { useFlowStore } from '../../store/flowStore';
import './WelcomeTour.css';

/** Step indices for interactive steps */
const DRAG_STEP = 2;
const CMD_K_STEP = 6;

export function WelcomeTour() {
  const { isActive, currentStep, hasCompleted, startTour, nextStep, prevStep, closeTour } =
    useTourStore();

  const [exiting, setExiting] = useState(false);
  const [spotlight, setSpotlight] = useState<SpotlightRect | null>(null);

  // Track whether user has completed the interactive action
  const nodeCountRef = useRef<number>(0);

  // Auto-launch on first visit after 800ms
  useEffect(() => {
    if (hasCompleted) return;
    const timer = setTimeout(() => {
      startTour();
    }, 800);
    return () => clearTimeout(timer);
  }, [hasCompleted, startTour]);

  // Recalculate spotlight when step changes
  const step = TOUR_STEPS[currentStep];
  useEffect(() => {
    if (!isActive || !step) return;
    const timer = setTimeout(() => {
      setSpotlight(getTargetRect(step.target));
    }, 50);
    return () => clearTimeout(timer);
  }, [isActive, currentStep, step]);

  // Recalculate on resize
  useEffect(() => {
    if (!isActive) return;
    const handleResize = () => {
      setSpotlight(getTargetRect(TOUR_STEPS[currentStep]?.target ?? null));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isActive, currentStep]);

  const handleNext = useCallback(() => {
    nextStep(TOUR_STEPS.length);
  }, [nextStep]);

  const handlePrev = useCallback(() => {
    prevStep();
  }, [prevStep]);

  const handleClose = useCallback(() => {
    setExiting(true);
    setTimeout(() => {
      closeTour(currentStep >= TOUR_STEPS.length - 1);
      setExiting(false);
    }, 300);
  }, [closeTour, currentStep]);

  const handleSkip = useCallback(() => {
    setExiting(true);
    setTimeout(() => {
      closeTour(true);
      setExiting(false);
    }, 300);
  }, [closeTour]);

  // ── Auto-advance on interactive steps when user adds a node ─────────────────
  useEffect(() => {
    if (!isActive) return;
    const isInteractiveStep = currentStep === DRAG_STEP || currentStep === CMD_K_STEP;
    if (!isInteractiveStep) return;

    // Snapshot current node count
    nodeCountRef.current = useFlowStore.getState().nodes.length;

    const unsub = useFlowStore.subscribe((state) => {
      if (state.nodes.length > nodeCountRef.current) {
        // User added a node — auto-advance after a brief pause for the drop animation
        setTimeout(() => {
          nextStep(TOUR_STEPS.length);
        }, 400);
        unsub();
      }
    });

    return unsub;
  }, [isActive, currentStep, nextStep]);

  // ── Keyboard navigation ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isActive) return;

    const handler = (e: KeyboardEvent) => {
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;

      // On the ⌘K interactive step, let ⌘K through to open the command palette
      if (currentStep === CMD_K_STEP && isCtrlOrMeta && e.key === 'k') {
        // Don't intercept — let it bubble to FlowCanvas's handler
        return;
      }

      // On interactive steps, also let Enter and Escape through when the
      // command palette is open (its modal is in the DOM)
      if (currentStep === CMD_K_STEP) {
        const paletteOpen = document.querySelector('.command-palette__modal');
        if (paletteOpen) {
          // Let all keys pass through to the palette
          return;
        }
      }

      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        e.stopPropagation();
        handlePrev();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        handleClose();
      }
    };

    document.addEventListener('keydown', handler, true);
    return () => document.removeEventListener('keydown', handler, true);
  }, [isActive, currentStep, handleNext, handlePrev, handleClose]);

  // ── Boost command palette z-index & auto-open during the ⌘K step ─────────────
  useEffect(() => {
    if (!isActive || currentStep !== CMD_K_STEP) return;

    const style = document.createElement('style');
    style.setAttribute('data-tour-cmd-k', '');
    style.textContent = `
      .command-palette__backdrop {
        z-index: 9002 !important;
        background: transparent !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
      }
      .command-palette__modal { z-index: 9003 !important; }
      .tour-tooltip { z-index: 9004 !important; }
    `;
    document.head.appendChild(style);

    // Auto-open the command palette after a short delay for the step transition
    const timer = setTimeout(() => {
      document.dispatchEvent(new CustomEvent('tour:open-palette'));
    }, 400);

    return () => {
      style.remove();
      clearTimeout(timer);
    };
  }, [isActive, currentStep]);

  if (!isActive && !exiting) return null;
  if (!step) return null;

  const isFirst = currentStep === 0;
  const isLast = currentStep === TOUR_STEPS.length - 1;

  return createPortal(
    <div className={`tour-wrapper ${exiting ? 'tour-wrapper--exiting' : ''}`}>
      <TourOverlay
        targetSelector={step.target}
        visible={true}
        allowInteraction={step.allowInteraction}
      />
      <TourTooltip
        step={step}
        stepIndex={currentStep}
        totalSteps={TOUR_STEPS.length}
        spotlight={spotlight}
        onNext={isLast ? handleClose : handleNext}
        onPrev={handlePrev}
        onSkip={handleSkip}
        isFirst={isFirst}
        isLast={isLast}
      />

      {/* Particle burst on finish step */}
      {isLast && (
        <div className="tour-tooltip__particles" style={{ position: 'fixed', inset: 0, zIndex: 9002, pointerEvents: 'none' }}>
          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i / 12) * Math.PI * 2;
            const distance = 60 + Math.random() * 40;
            return (
              <span
                key={i}
                className="tour-tooltip__particle"
                style={{
                  '--tx': `${Math.cos(angle) * distance}px`,
                  '--ty': `${Math.sin(angle) * distance}px`,
                  animationDelay: `${i * 50}ms`,
                } as React.CSSProperties}
              />
            );
          })}
        </div>
      )}
    </div>,
    document.body
  );
}
