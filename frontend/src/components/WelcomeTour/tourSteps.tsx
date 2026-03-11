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
  /** Optional illustration key rendered by TourTooltip */
  illustration?: 'time-range' | 'toggle-anomaly' | 'connect-pipeline' | 'results-table';
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);
const mod = isMac ? '⌘' : 'Ctrl';

export const TOUR_STEPS: TourStep[] = [
  // Step 0 — Welcome
  {
    target: null,
    title: 'Welcome to ONYX 12',
    description:
      'Build flight analysis pipelines visually — drag cubes, wire them together, execute. No code required.\n\nLet\u2019s build your first pipeline together.',
    position: 'center',
    hero: true,
  },
  // Step 1 — Name Your Workflow
  {
    target: 'workflow-name',
    title: 'Name Your Workflow',
    description:
      'Give your workflow a name — click the title and type something like "Anomaly Pipeline".\n\nYou can always rename it later.',
    position: 'bottom',
    allowInteraction: true,
  },
  // Step 2 — Cube Catalog
  {
    target: 'cube-catalog',
    title: 'Your Building Blocks',
    description:
      'Cubes are processing units grouped by type — data sources, filters, analysis, aggregation, and output.\n\nFind "All Flights" in the Data Source section — we\u2019ll use it first.',
    position: 'right',
  },
  // Step 3 — Drag All Flights (interactive)
  {
    target: 'cube-card',
    title: 'Drag All Flights',
    description:
      'Grab the All Flights cube and drop it onto the canvas. This cube queries flight metadata from the Tracer 42 database.\n\nThe tour continues automatically once you drop it.',
    position: 'right',
    allowInteraction: true,
  },
  // Step 4 — The Canvas
  {
    target: 'canvas',
    title: 'Your Workspace',
    description:
      'Pan by dragging the background. Zoom with scroll wheel. This is where your pipeline takes shape.',
    position: 'bottom',
    allowInteraction: true,
  },
  // Step 5 — Set Time Range (interactive — user can click on the cube)
  {
    target: 'canvas',
    title: 'Set the Time Range',
    description:
      'On your All Flights cube, find the time range field and set it to 90 days.\n\nThis pulls 3 months of flight data — enough to spot patterns in the anomaly analysis we\u2019re building.\n\nClick on the cube to configure it, then press Next.',
    position: 'bottom',
    allowInteraction: true,
    illustration: 'time-range',
  },
  // Step 6 — Command Palette: Add Get Anomalies (interactive)
  {
    target: null,
    title: `Add Anomalies with ${mod}+K`,
    description: `This is the command palette — the fastest way to add cubes.\nSearch for "Get Anomalies" and hit Enter to add it to your canvas.\n\nYou can open it anytime with ${mod}+K.`,
    position: 'center',
    allowInteraction: true,
  },
  // Step 7 — Toggle is_anomaly (interactive — user can click on the cube)
  {
    target: 'canvas',
    title: 'Filter Anomalies Only',
    description:
      'On the Get Anomalies cube, find the is_anomaly toggle and check it.\n\nThis filters results to only confirmed anomalous flights — the ones flagged by the detection system.\n\nToggle it, then press Next.',
    position: 'bottom',
    allowInteraction: true,
    illustration: 'toggle-anomaly',
  },
  // Step 8 — Connect the Pipeline (interactive — user can drag handles)
  {
    target: 'canvas',
    title: 'Connect the Pipeline',
    description:
      'Now wire them together! Drag from the "flight_ids" output on All Flights (right side) to the "flight_ids" input on Get Anomalies (left side).\n\nHandle colors show parameter types — matching colors mean compatible types.\n\nConnect them, then press Next.',
    position: 'bottom',
    allowInteraction: true,
    illustration: 'connect-pipeline',
  },
  // Step 9 — Run (interactive — user clicks Run, auto-advances when execution completes)
  {
    target: 'run-btn',
    title: 'Run Your Pipeline',
    description: `Hit Run to execute! All Flights fetches the data first, then Get Anomalies processes the connected flight IDs.\n\nWatch the cubes light up as they execute.\nShortcut: ${mod}+Enter`,
    position: 'bottom',
    allowInteraction: true,
  },
  // Step 10 — View Results (auto-opened by tour after execution completes)
  {
    target: 'results-drawer',
    title: 'Anomaly Results',
    description:
      'Here are the anomaly reports from your pipeline. Each row is a flagged flight.\n\nYou can click any cube\u2019s header to switch between results — try clicking All Flights to see the raw flight data.',
    position: 'top',
    illustration: 'results-table',
  },
  // Step 11 — Shortcuts Overview
  {
    target: 'help-btn',
    title: 'Power Shortcuts',
    description: `${mod}+S Save \u00B7 ${mod}+Enter Run \u00B7 ${mod}+Z Undo \u00B7 ${mod}+Shift+Z Redo \u00B7 ${mod}+K Command Palette \u00B7 Del Delete \u00B7 ? Shortcuts panel`,
    position: 'bottom',
  },
  // Step 12 — Finish
  {
    target: null,
    title: "You're Ready",
    description:
      'Your first pipeline is built! Experiment with more cubes, add filters, and build complex analysis workflows.\n\nReopen this tour anytime from the ? menu.',
    position: 'center',
    hero: true,
  },
];
