import { Platform } from 'react-native';

/**
 * Non-colour design tokens. These are scheme-independent and are the single
 * source of truth for every measurement in the application. Screens must never
 * introduce raw numbers for spacing, radius, or type size.
 */

/** 4pt base grid. */
export const spacing = {
  none: 0,
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  huge: 40,
  giant: 56,
} as const;

/**
 * Rounded enough to read as a product surface rather than an instrument panel.
 *
 * The scale is proportional: small controls take `sm`/`md`, cards and panels
 * take `lg`/`xl`, and sheets take `xxl`. Radii that do not scale with the
 * element are what make an interface look assembled from parts — a 6pt corner
 * on a 240pt card reads as an oversight.
 */
export const radii = {
  none: 0,
  xs: 4,
  sm: 6,
  md: 10,
  lg: 14,
  xl: 18,
  xxl: 24,
  pill: 999,
} as const;

export const borderWidth = {
  none: 0,
  hairline: Platform.select({ ios: 0.5, default: 0.8 }) as number,
  thin: 1,
  medium: 1.5,
  thick: 2,
  heavy: 3,
} as const;

export const fontSize = {
  micro: 10,
  caption: 11,
  small: 12,
  body: 14,
  bodyLarge: 15,
  subtitle: 17,
  title: 20,
  headline: 24,
  display: 30,
  hero: 40,
  metric: 48,
} as const;

export const lineHeight = {
  micro: 14,
  caption: 15,
  small: 17,
  body: 20,
  bodyLarge: 22,
  subtitle: 24,
  title: 26,
  headline: 30,
  display: 36,
  hero: 46,
  metric: 52,
} as const;

export const fontWeight = {
  regular: '400',
  medium: '500',
  semibold: '600',
  bold: '700',
} as const;

/**
 * Data values (document numbers, MRZ lines, case identifiers, hashes) are set in
 * a monospaced face so that character-level differences are legible at a glance.
 * This is a functional choice, not a decorative one.
 */
export const fontFamily = {
  system: Platform.select({ ios: 'System', android: 'sans-serif', default: 'System' }) as string,
  systemMedium: Platform.select({
    ios: 'System',
    android: 'sans-serif-medium',
    default: 'System',
  }) as string,
  mono: Platform.select({
    ios: 'Menlo',
    android: 'monospace',
    default: 'monospace',
  }) as string,
} as const;

/** Letter spacing for the uppercase micro-labels used throughout the console. */
export const letterSpacing = {
  tight: -0.4,
  normal: 0,
  wide: 0.4,
  wider: 0.8,
  widest: 1.2,
} as const;

export const iconSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
} as const;

export const controlHeight = {
  /** Minimum accessible touch target. Never go below this for interactive rows. */
  minTouchTarget: 44,
  small: 32,
  medium: 40,
  large: 48,
  xlarge: 56,
} as const;

export const duration = {
  instant: 0,
  fast: 120,
  normal: 200,
  slow: 320,
  deliberate: 480,
} as const;

/** Elevation is expressed as a token so light/dark can render it differently. */
export const elevationLevel = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
} as const;

export const opacity = {
  disabled: 0.4,
  muted: 0.6,
  pressed: 0.7,
  overlay: 0.72,
  scrim: 0.85,
} as const;

/** Breakpoints in dp of the shortest screen edge. */
export const breakpoint = {
  compact: 0,
  medium: 600,
  expanded: 840,
} as const;

export type Spacing = keyof typeof spacing;
export type Radius = keyof typeof radii;
export type FontSize = keyof typeof fontSize;
export type ElevationLevel = keyof typeof elevationLevel;
