/**
 * Colour is used sparingly and always carries meaning. Four semantic channels:
 *
 *   POSITIVE  green   pass / cleared / synced
 *   CAUTION   amber   review / warning / pending
 *   CRITICAL  red     failure / high risk / rejected
 *   INFO      blue    system state / neutral information
 *
 * Every status is additionally carried by an icon glyph and a text label, so the
 * interface remains fully legible without colour perception.
 */

export interface SemanticPalette {
  /** Page background, furthest back. */
  canvas: string;
  /** Default panel surface. */
  surface: string;
  /** Raised surface (sheets, popovers, active rows). */
  surfaceRaised: string;
  /** Recessed surface (inputs, wells, code blocks). */
  surfaceSunken: string;
  /** Surface used for camera chrome and full-bleed media backdrops. */
  surfaceInverse: string;

  border: string;
  borderStrong: string;
  borderFocus: string;

  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  textInverse: string;
  textOnAccent: string;

  accent: string;
  accentPressed: string;
  accentSubtle: string;
  accentBorder: string;

  positive: string;
  positiveSubtle: string;
  positiveBorder: string;

  caution: string;
  cautionSubtle: string;
  cautionBorder: string;

  critical: string;
  criticalPressed: string;
  criticalSubtle: string;
  criticalBorder: string;

  info: string;
  infoSubtle: string;
  infoBorder: string;

  /** Neutral "inactive / not started" channel for pipeline steps. */
  neutral: string;
  neutralSubtle: string;
  neutralBorder: string;

  /** Scrims and overlays. */
  scrim: string;
  overlay: string;

  /** Forensic region overlay ramp — low to high suspicion. */
  heatLow: string;
  heatMedium: string;
  heatHigh: string;

  /** Skeleton loading shimmer base. */
  skeleton: string;
}

export const darkPalette: SemanticPalette = {
  canvas: '#0B1017',
  surface: '#121A24',
  surfaceRaised: '#18222E',
  surfaceSunken: '#080D13',
  surfaceInverse: '#000000',

  border: '#243040',
  borderStrong: '#35455A',
  borderFocus: '#5B9DF9',

  textPrimary: '#E8EDF3',
  textSecondary: '#9FB0C2',
  textTertiary: '#6B7F94',
  textInverse: '#0B1017',
  textOnAccent: '#FFFFFF',

  accent: '#3B82F6',
  accentPressed: '#2563EB',
  accentSubtle: '#12243F',
  accentBorder: '#1E4A85',

  positive: '#34D399',
  positiveSubtle: '#0C2A22',
  positiveBorder: '#155E4A',

  caution: '#FBBF24',
  cautionSubtle: '#2C2210',
  cautionBorder: '#6B4E11',

  critical: '#F87171',
  criticalPressed: '#EF4444',
  criticalSubtle: '#2E1416',
  criticalBorder: '#7A2A2E',

  info: '#60A5FA',
  infoSubtle: '#101F33',
  infoBorder: '#1E456F',

  neutral: '#7C8FA3',
  neutralSubtle: '#161F2A',
  neutralBorder: '#2C3A4B',

  scrim: 'rgba(3, 6, 10, 0.72)',
  overlay: 'rgba(3, 6, 10, 0.55)',

  heatLow: 'rgba(96, 165, 250, 0.28)',
  heatMedium: 'rgba(251, 191, 36, 0.32)',
  heatHigh: 'rgba(248, 113, 113, 0.38)',

  skeleton: '#1B2634',
};

/**
 * The default scheme.
 *
 * Tuned for a calm, product-grade surface rather than the high-contrast
 * instrument look: a warm off-white ground so white cards lift off it without
 * needing heavy borders, one confident indigo accent, and status colours that
 * stay legible as small text on their own tinted backgrounds. Greys carry a
 * slight blue cast so neutrals read as considered rather than muddy.
 */
export const lightPalette: SemanticPalette = {
  canvas: '#F7F8FA',
  surface: '#FFFFFF',
  surfaceRaised: '#FFFFFF',
  surfaceSunken: '#F1F3F7',
  surfaceInverse: '#111827',

  // Borders sit close to the ground tone: separation comes from elevation and
  // whitespace, and a hard rule around every card is what makes an interface
  // look like a form rather than a product.
  border: '#E8EBF0',
  borderStrong: '#D3D8E0',
  borderFocus: '#4F46E5',

  textPrimary: '#111827',
  textSecondary: '#5A6474',
  textTertiary: '#8A94A6',
  textInverse: '#FFFFFF',
  textOnAccent: '#FFFFFF',

  accent: '#4F46E5',
  accentPressed: '#4338CA',
  accentSubtle: '#EEF0FE',
  accentBorder: '#C9CCF8',

  positive: '#047857',
  positiveSubtle: '#ECFDF5',
  positiveBorder: '#A7E8CD',

  caution: '#B45309',
  cautionSubtle: '#FFF8EB',
  cautionBorder: '#F2D9A8',

  critical: '#DC2626',
  criticalPressed: '#B91C1C',
  criticalSubtle: '#FEF2F2',
  criticalBorder: '#F6C2C2',

  info: '#4F46E5',
  infoSubtle: '#EEF0FE',
  infoBorder: '#C9CCF8',

  neutral: '#6B7280',
  neutralSubtle: '#F3F4F8',
  neutralBorder: '#E2E6ED',

  scrim: 'rgba(17, 24, 39, 0.45)',
  overlay: 'rgba(17, 24, 39, 0.28)',

  heatLow: 'rgba(79, 70, 229, 0.18)',
  heatMedium: 'rgba(180, 83, 9, 0.24)',
  heatHigh: 'rgba(220, 38, 38, 0.30)',

  skeleton: '#EDEFF3',
};
