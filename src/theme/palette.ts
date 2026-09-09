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

export const lightPalette: SemanticPalette = {
  canvas: '#EEF1F5',
  surface: '#FFFFFF',
  surfaceRaised: '#FFFFFF',
  surfaceSunken: '#F3F5F8',
  surfaceInverse: '#000000',

  border: '#D7DEE6',
  borderStrong: '#B4C0CC',
  borderFocus: '#1D4ED8',

  textPrimary: '#0F1923',
  textSecondary: '#4A5C6E',
  textTertiary: '#6F8296',
  textInverse: '#FFFFFF',
  textOnAccent: '#FFFFFF',

  accent: '#1D4ED8',
  accentPressed: '#1E40AF',
  accentSubtle: '#EAF0FE',
  accentBorder: '#B9CDF6',

  positive: '#15803D',
  positiveSubtle: '#E9F6EE',
  positiveBorder: '#A8D8BB',

  caution: '#A15C07',
  cautionSubtle: '#FDF3E2',
  cautionBorder: '#EBCE96',

  critical: '#B91C1C',
  criticalPressed: '#991B1B',
  criticalSubtle: '#FCECEC',
  criticalBorder: '#EFB4B4',

  info: '#1D4ED8',
  infoSubtle: '#EAF0FE',
  infoBorder: '#B9CDF6',

  neutral: '#607287',
  neutralSubtle: '#F0F3F6',
  neutralBorder: '#CFD8E1',

  scrim: 'rgba(15, 25, 35, 0.55)',
  overlay: 'rgba(15, 25, 35, 0.35)',

  heatLow: 'rgba(29, 78, 216, 0.22)',
  heatMedium: 'rgba(161, 92, 7, 0.28)',
  heatHigh: 'rgba(185, 28, 28, 0.34)',

  skeleton: '#E3E8ED',
};
