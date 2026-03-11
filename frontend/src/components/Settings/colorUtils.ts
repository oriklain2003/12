/** Utility functions for theme color manipulation. */

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}

export function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
}

/** Blend a color toward white by `amount` (0-1). */
export function lighten(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(
    r + (255 - r) * amount,
    g + (255 - g) * amount,
    b + (255 - b) * amount,
  );
}

/** Blend a color toward black by `amount` (0-1). */
export function darken(hex: string, amount: number): string {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r * (1 - amount), g * (1 - amount), b * (1 - amount));
}

/**
 * Derive all CSS variable values from a single accent hex color.
 * Returns a map of CSS property name -> value.
 */
export function deriveAccentVariants(hex: string): Record<string, string> {
  const [r, g, b] = hexToRgb(hex);
  const rgb = `${r}, ${g}, ${b}`;

  const hoverHex = lighten(hex, 0.25);
  const [hr, hg, hb] = hexToRgb(hoverHex);
  const hoverRgb = `${hr}, ${hg}, ${hb}`;

  const darkHex = darken(hex, 0.22);
  const [dr, dg, db] = hexToRgb(darkHex);

  return {
    '--accent-rgb': rgb,
    '--accent-hover-rgb': hoverRgb,
    '--color-accent': hex,
    '--color-accent-hover': hoverHex,
    '--color-accent-glow': `rgba(${rgb}, 0.35)`,
    '--color-border-focus': `rgba(${rgb}, 0.5)`,
    '--btn-accent-bg': `rgba(${rgb}, 0.18)`,
    '--btn-accent-border': `rgba(${rgb}, 0.25)`,
    '--btn-accent-border-top': `rgba(${hoverRgb}, 0.35)`,
    '--btn-accent-border-bottom': `rgba(${dr}, ${dg}, ${db}, 0.15)`,
    '--shadow-node-selected': `0 0 0 2px ${hex}, 0 8px 40px rgba(${rgb}, 0.2)`,
    '--shadow-glow-accent': `0 0 20px rgba(${rgb}, 0.3), 0 0 40px rgba(${rgb}, 0.1)`,
  };
}
