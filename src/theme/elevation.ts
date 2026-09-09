import { Platform, type ViewStyle } from 'react-native';

import type { ElevationLevel } from './tokens';
import type { ColorScheme } from './types';

/**
 * Shadows are deliberately restrained. In dark mode a drop shadow is nearly
 * invisible, so elevation there is carried by surface tone and border contrast
 * instead — which is also cheaper to render.
 */
export function elevation(level: ElevationLevel, scheme: ColorScheme): ViewStyle {
  if (level === 'none') return {};
  if (scheme === 'dark') {
    // Dark UI: rely on tone separation, add only a faint ambient shadow.
    const opacityByLevel = { low: 0.18, medium: 0.28, high: 0.38 } as const;
    const radiusByLevel = { low: 4, medium: 10, high: 20 } as const;
    return Platform.select<ViewStyle>({
      android: { elevation: level === 'low' ? 1 : level === 'medium' ? 3 : 6 },
      default: {
        shadowColor: '#000000',
        shadowOpacity: opacityByLevel[level],
        shadowRadius: radiusByLevel[level],
        shadowOffset: { width: 0, height: level === 'low' ? 1 : level === 'medium' ? 4 : 8 },
      },
    }) as ViewStyle;
  }

  const opacityByLevel = { low: 0.05, medium: 0.08, high: 0.12 } as const;
  const radiusByLevel = { low: 3, medium: 8, high: 18 } as const;
  return Platform.select<ViewStyle>({
    android: { elevation: level === 'low' ? 1 : level === 'medium' ? 3 : 6 },
    default: {
      shadowColor: '#0F1923',
      shadowOpacity: opacityByLevel[level],
      shadowRadius: radiusByLevel[level],
      shadowOffset: { width: 0, height: level === 'low' ? 1 : level === 'medium' ? 3 : 6 },
    },
  }) as ViewStyle;
}
