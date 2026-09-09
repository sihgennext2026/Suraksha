import type { SemanticPalette } from './palette';
import type {
  borderWidth,
  controlHeight,
  duration,
  fontFamily,
  fontSize,
  fontWeight,
  iconSize,
  letterSpacing,
  lineHeight,
  opacity,
  radii,
  spacing,
} from './tokens';

export type ColorScheme = 'light' | 'dark';
export type ThemePreference = ColorScheme | 'system';

export interface Theme {
  scheme: ColorScheme;
  color: SemanticPalette;
  spacing: typeof spacing;
  radii: typeof radii;
  borderWidth: typeof borderWidth;
  fontSize: typeof fontSize;
  lineHeight: typeof lineHeight;
  fontWeight: typeof fontWeight;
  fontFamily: typeof fontFamily;
  letterSpacing: typeof letterSpacing;
  iconSize: typeof iconSize;
  controlHeight: typeof controlHeight;
  duration: typeof duration;
  opacity: typeof opacity;
}
