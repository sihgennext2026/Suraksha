import React, { createContext, useContext, useMemo, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';

import { darkPalette, lightPalette } from './palette';
import {
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
import type { ColorScheme, Theme, ThemePreference } from './types';

function buildTheme(scheme: ColorScheme): Theme {
  return {
    scheme,
    color: scheme === 'dark' ? darkPalette : lightPalette,
    spacing,
    radii,
    borderWidth,
    fontSize,
    lineHeight,
    fontWeight,
    fontFamily,
    letterSpacing,
    iconSize,
    controlHeight,
    duration,
    opacity,
  };
}

const darkTheme = buildTheme('dark');
const lightTheme = buildTheme('light');

// Light is the product's default surface; dark remains available for night
// duty at a post, where a bright screen is a liability.
const ThemeContext = createContext<Theme>(lightTheme);

interface ThemeProviderProps {
  preference: ThemePreference;
  children: ReactNode;
}

export function ThemeProvider({ preference, children }: ThemeProviderProps) {
  const systemScheme = useColorScheme();
  const theme = useMemo(() => {
    const resolved: ColorScheme =
      preference === 'system' ? (systemScheme === 'light' ? 'light' : 'dark') : preference;
    return resolved === 'dark' ? darkTheme : lightTheme;
  }, [preference, systemScheme]);

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  return useContext(ThemeContext);
}

/**
 * Builds a StyleSheet-shaped object from the active theme, memoised per theme.
 * Keeps style construction out of render bodies without losing theme awareness.
 */
export function useThemedStyles<T>(factory: (theme: Theme) => T): T {
  const theme = useTheme();
  return useMemo(() => factory(theme), [theme, factory]);
}

export { buildTheme };
