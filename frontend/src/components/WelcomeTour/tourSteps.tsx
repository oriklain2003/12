/**
 * Tour step definitions — target selectors, content, and tooltip positioning.
 */

export interface TourStep {
  /** data-tour attribute value to target, or null for centered modal */
  target: string | null;
  title: string;
  description: string;
  /** Preferred tooltip position relative to the spotlight */
  position: 'top' | 'bottom' | 'left' | 'right' | 'center';
  /** Allow user to interact with the spotlighted element (pointer events pass through) */
  allowInteraction?: boolean;
  /** Whether this is the welcome or finish step (centered, large) */
  hero?: boolean;
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);
const mod = isMac ? '⌘' : 'Ctrl';

export const TOUR_STEPS: TourStep[] = [
  // Step 0 — Welcome
  {
    target: null,
    title: 'Welcome to ONYX 12',
    description:
      'Build flight analysis pipelines visually — drag cubes, wire them together, execute. No code required.',
    position: 'center',
    hero: true,
  },
  // Step 1 — Cube Catalog
  {
    target: 'cube-catalog',
    title: 'Your Building Blocks',
    description:
      'Cubes are processing units grouped by type — data sources, filters, analysis, aggregation, and output. Search to find what you need, or browse by category.',
    position: 'right',
  },
  // Step 2 — Drag to Build (interactive — user can drag the cube)
  {
    target: 'cube-card',
    title: 'Drag & Drop',
    description:
      'Try it! Grab this cube and drop it onto the canvas. The tour will continue automatically.',
    position: 'right',
    allowInteraction: true,
  },
  // Step 3 — The Canvas
  {
    target: 'canvas',
    title: 'Your Workspace',
    description:
      'Pan by dragging the background. Zoom with scroll wheel. This is where your pipeline takes shape.',
    position: 'bottom',
    allowInteraction: true,
  },
  // Step 4 — Connections (conceptual, no target)
  {
    target: null,
    title: 'Wire It Up',
    description:
      'Drag from an output handle on the right to an input handle on the left. Colors show parameter types. Mismatches are allowed but flagged.',
    position: 'center',
  },
  // Step 5 — Save & Run
  {
    target: 'save-btn',
    title: 'Save & Execute',
    description: `Save your workflow, then hit Run. Watch cubes light up as they execute. Results appear on each cube and in the bottom drawer.\n\nShortcuts: ${mod}+S to save, ${mod}+Enter to run.`,
    position: 'bottom',
  },
  // Step 6 — Command Palette (interactive — opens automatically)
  {
    target: null,
    title: `Quick Add with ${mod}+K`,
    description: `This is the command palette — the fastest way to add cubes. Search for a cube and hit Enter to add it! You can open it anytime with ${mod}+K.`,
    position: 'center',
    allowInteraction: true,
  },
  // Step 7 — Shortcuts Overview
  {
    target: 'help-btn',
    title: 'Power Shortcuts',
    description: `${mod}+S Save · ${mod}+Enter Run · ${mod}+Z Undo · ${mod}+Shift+Z Redo · ${mod}+K Command Palette · Del Delete · ? Shortcuts panel`,
    position: 'bottom',
  },
  // Step 8 — Finish
  {
    target: null,
    title: "You're Ready",
    description:
      'Start building your first workflow. Reopen this tour anytime from the ? menu.',
    position: 'center',
    hero: true,
  },
];
