import React, { useMemo } from 'react';
import { Text as RNText, type TextProps as RNTextProps, type TextStyle } from 'react-native';

import { useTheme } from '@/theme';
import type { SemanticPalette } from '@/theme';

/**
 * The single text primitive. Screens choose a role, never a font size — which is
 * what keeps typography consistent across forty-odd screens and makes a global
 * type change one edit.
 */
export type TextRole =
  /** Screen titles. */
  | 'headline'
  /** Section and panel titles. */
  | 'title'
  /** Sub-section headings inside a panel. */
  | 'subtitle'
  /** Default running text. */
  | 'body'
  /** Slightly larger body, for the one sentence that matters most on a screen. */
  | 'bodyLarge'
  /** Secondary supporting text. */
  | 'caption'
  /** Uppercase micro-label above a value or section. */
  | 'label'
  /** Large numeric read-out. */
  | 'metric'
  /** Monospaced data value: document numbers, MRZ lines, case references. */
  | 'mono'
  /** Small monospaced value. */
  | 'monoSmall';

export type TextTone =
  | 'primary'
  | 'secondary'
  | 'tertiary'
  | 'accent'
  | 'positive'
  | 'caution'
  | 'critical'
  | 'info'
  | 'inverse'
  | 'onAccent';

/**
 * RN's own `role` prop (the ARIA role) is deliberately omitted: this component
 * uses `role` for the typographic role, and accessibility semantics are set
 * through `accessibilityRole`, which is the prop the rest of the app uses.
 */
export interface TextProps extends Omit<RNTextProps, 'role'> {
  role?: TextRole;
  tone?: TextTone;
  /** Overrides the role's default weight when emphasis is needed. */
  weight?: 'regular' | 'medium' | 'semibold' | 'bold';
  align?: TextStyle['textAlign'];
  children?: React.ReactNode;
}

const TONE_KEY: Record<TextTone, keyof SemanticPalette> = {
  primary: 'textPrimary',
  secondary: 'textSecondary',
  tertiary: 'textTertiary',
  accent: 'accent',
  positive: 'positive',
  caution: 'caution',
  critical: 'critical',
  info: 'info',
  inverse: 'textInverse',
  onAccent: 'textOnAccent',
};

export function Text({
  role = 'body',
  tone = 'primary',
  weight,
  align,
  style,
  children,
  ...rest
}: TextProps) {
  const theme = useTheme();

  const composed = useMemo<TextStyle>(() => {
    const base: Record<TextRole, TextStyle> = {
      headline: {
        fontSize: theme.fontSize.headline,
        lineHeight: theme.lineHeight.headline,
        fontWeight: theme.fontWeight.bold,
        letterSpacing: theme.letterSpacing.tight,
      },
      title: {
        fontSize: theme.fontSize.title,
        lineHeight: theme.lineHeight.title,
        fontWeight: theme.fontWeight.semibold,
        letterSpacing: theme.letterSpacing.tight,
      },
      subtitle: {
        fontSize: theme.fontSize.subtitle,
        lineHeight: theme.lineHeight.subtitle,
        fontWeight: theme.fontWeight.semibold,
      },
      body: {
        fontSize: theme.fontSize.body,
        lineHeight: theme.lineHeight.body,
        fontWeight: theme.fontWeight.regular,
      },
      bodyLarge: {
        fontSize: theme.fontSize.bodyLarge,
        lineHeight: theme.lineHeight.bodyLarge,
        fontWeight: theme.fontWeight.regular,
      },
      caption: {
        fontSize: theme.fontSize.small,
        lineHeight: theme.lineHeight.small,
        fontWeight: theme.fontWeight.regular,
      },
      label: {
        fontSize: theme.fontSize.caption,
        lineHeight: theme.lineHeight.caption,
        fontWeight: theme.fontWeight.semibold,
        letterSpacing: theme.letterSpacing.widest,
        textTransform: 'uppercase',
      },
      metric: {
        fontSize: theme.fontSize.metric,
        lineHeight: theme.lineHeight.metric,
        fontWeight: theme.fontWeight.bold,
        letterSpacing: theme.letterSpacing.tight,
        fontVariant: ['tabular-nums'],
      },
      mono: {
        fontFamily: theme.fontFamily.mono,
        fontSize: theme.fontSize.bodyLarge,
        lineHeight: theme.lineHeight.bodyLarge,
        letterSpacing: theme.letterSpacing.wide,
      },
      monoSmall: {
        fontFamily: theme.fontFamily.mono,
        fontSize: theme.fontSize.small,
        lineHeight: theme.lineHeight.small,
        letterSpacing: theme.letterSpacing.wide,
      },
    };

    return {
      ...base[role],
      color: theme.color[TONE_KEY[tone]],
      ...(weight ? { fontWeight: theme.fontWeight[weight] } : null),
      ...(align ? { textAlign: align } : null),
    };
  }, [theme, role, tone, weight, align]);

  return (
    <RNText style={[composed, style]} {...rest}>
      {children}
    </RNText>
  );
}
