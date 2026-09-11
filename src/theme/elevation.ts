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

  // Light UI: the shadow is what separates a card from the ground, since the
  // borders are deliberately close in tone. Wide and faint reads as depth; tight
  // and dark reads as a drop-shadow effect.
  const opacityByLevel = { low: 0.04, medium: 0.07, high: 0.10 } as const;
  const radiusByLevel = { low: 6, medium: 16, high: 32 } as const;
  return Platform.select<ViewStyle>({
    android: { elevation: level === 'low' ? 1 : level === 'medium' ? 4 : 8 },
    default: {
      shadowColor: '#101828',
      shadowOpacity: opacityByLevel[level],
      shadowRadius: radiusByLevel[level],
      shadowOffset: { width: 0, height: level === 'low' ? 1 : level === 'medium' ? 6 : 12 },
    },
  }) as ViewStyle;
}
