import { useWindowDimensions } from 'react-native';

import { breakpoint } from '@/theme';

export type SizeClass = 'compact' | 'medium' | 'expanded';

export interface Responsive {
  width: number;
  height: number;
  sizeClass: SizeClass;
  /** True on tablets and large foldables. */
  isTablet: boolean;
  /** Columns for the dashboard and metric grids at this width. */
  gridColumns: number;
  /** Constrains reading measure on wide screens so lines stay scannable. */
  contentMaxWidth: number;
  /** Face comparison and document/live pairs sit side by side when true. */
  canPairHorizontally: boolean;
}

/**
 * Layout decisions are derived from the shortest screen edge rather than raw
 * width, so a phone held in landscape does not get a tablet layout it has no
 * vertical room for.
 */
export function useResponsive(): Responsive {
  const { width, height } = useWindowDimensions();
  const shortestEdge = Math.min(width, height);

  const sizeClass: SizeClass =
    shortestEdge >= breakpoint.expanded
      ? 'expanded'
      : shortestEdge >= breakpoint.medium
        ? 'medium'
        : 'compact';

  const isTablet = sizeClass !== 'compact';

  return {
    width,
    height,
    sizeClass,
    isTablet,
    gridColumns: sizeClass === 'expanded' ? 3 : sizeClass === 'medium' ? 2 : 2,
    contentMaxWidth: sizeClass === 'expanded' ? 760 : sizeClass === 'medium' ? 640 : width,
    canPairHorizontally: width >= 520,
  };
}
