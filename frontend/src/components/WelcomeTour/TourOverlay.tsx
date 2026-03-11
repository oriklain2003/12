/**
 * Full-viewport overlay with masked spotlight cutout.
 *
 * Two rendering modes:
 * - Default: SVG with <mask> — visual spotlight, blocks pointer events
 *   outside the tooltip (but does NOT close the tour on click)
 * - Interactive (allowInteraction): pointer-events: none on the entire
 *   overlay so the user can freely interact with the page underneath
 *   (drag cubes, use command palette, etc.)
 */

import { useEffect, useState, useCallback } from 'react';

interface SpotlightRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface TourOverlayProps {
  targetSelector: string | null;
  visible: boolean;
  /** When true, entire overlay is pointer-events: none */
  allowInteraction?: boolean;
}

const PADDING = 12;
const BORDER_RADIUS = 14;

function getTargetRect(selector: string | null): SpotlightRect | null {
  if (!selector) return null;
  const el = document.querySelector(`[data-tour="${selector}"]`);
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return {
    x: rect.left - PADDING,
    y: rect.top - PADDING,
    width: rect.width + PADDING * 2,
    height: rect.height + PADDING * 2,
  };
}

export function TourOverlay({ targetSelector, visible, allowInteraction }: TourOverlayProps) {
  const [spotlight, setSpotlight] = useState<SpotlightRect | null>(null);

  const recalculate = useCallback(() => {
    setSpotlight(getTargetRect(targetSelector));
  }, [targetSelector]);

  useEffect(() => {
    recalculate();
  }, [recalculate]);

  // Recalculate on resize/scroll
  useEffect(() => {
    if (!targetSelector) return;
    window.addEventListener('resize', recalculate);
    window.addEventListener('scroll', recalculate, true);
    return () => {
      window.removeEventListener('resize', recalculate);
      window.removeEventListener('scroll', recalculate, true);
    };
  }, [targetSelector, recalculate]);

  if (!visible) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;

  // Interactive mode: visual-only overlay, pointer events pass through everything
  if (allowInteraction) {
    return (
      <svg
        className="tour-overlay tour-overlay--interactive"
        width={vw}
        height={vh}
        viewBox={`0 0 ${vw} ${vh}`}
        style={{ pointerEvents: 'none' }}
      >
        {/* Dark backdrop — visual only */}
        {spotlight ? (
          <>
            <defs>
              <mask id="tour-spotlight-mask-interactive">
                <rect x="0" y="0" width={vw} height={vh} fill="white" />
                <rect
                  className="tour-overlay__cutout"
                  x={spotlight.x}
                  y={spotlight.y}
                  width={spotlight.width}
                  height={spotlight.height}
                  rx={BORDER_RADIUS}
                  ry={BORDER_RADIUS}
                  fill="black"
                />
              </mask>
            </defs>
            <rect
              x="0" y="0" width={vw} height={vh}
              fill="rgba(0,0,0,0.55)"
              mask="url(#tour-spotlight-mask-interactive)"
            />
            <rect
              className="tour-overlay__glow"
              x={spotlight.x} y={spotlight.y}
              width={spotlight.width} height={spotlight.height}
              rx={BORDER_RADIUS} ry={BORDER_RADIUS}
              fill="none"
              stroke="rgba(99, 102, 241, 0.4)"
              strokeWidth="2"
            />
          </>
        ) : (
          <rect x="0" y="0" width={vw} height={vh} fill="rgba(0,0,0,0.55)" />
        )}
      </svg>
    );
  }

  // Default: SVG mask approach (blocks pointer events, but no click-to-close)
  return (
    <svg
      className={`tour-overlay ${spotlight ? '' : 'tour-overlay--no-spotlight'}`}
      width={vw}
      height={vh}
      viewBox={`0 0 ${vw} ${vh}`}
    >
      <defs>
        <mask id="tour-spotlight-mask">
          <rect x="0" y="0" width={vw} height={vh} fill="white" />
          {spotlight && (
            <rect
              className="tour-overlay__cutout"
              x={spotlight.x}
              y={spotlight.y}
              width={spotlight.width}
              height={spotlight.height}
              rx={BORDER_RADIUS}
              ry={BORDER_RADIUS}
              fill="black"
            />
          )}
        </mask>
      </defs>

      {/* Dark backdrop with spotlight hole */}
      <rect
        x="0"
        y="0"
        width={vw}
        height={vh}
        fill="rgba(0,0,0,0.7)"
        mask="url(#tour-spotlight-mask)"
      />

      {/* Glowing ring around spotlight */}
      {spotlight && (
        <rect
          className="tour-overlay__glow"
          x={spotlight.x}
          y={spotlight.y}
          width={spotlight.width}
          height={spotlight.height}
          rx={BORDER_RADIUS}
          ry={BORDER_RADIUS}
          fill="none"
          stroke="rgba(99, 102, 241, 0.4)"
          strokeWidth="2"
        />
      )}
    </svg>
  );
}

export { getTargetRect };
export type { SpotlightRect };
