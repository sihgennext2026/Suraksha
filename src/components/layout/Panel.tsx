import React, { type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { elevation, useTheme } from '@/theme';

interface SectionProps {
  /** Uppercase micro-label introducing the group. */
  title?: string;
  /** One line of context under the title. */
  description?: string;
  /** Trailing control aligned with the title. */
  action?: ReactNode;
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}

/**
 * A titled group of content with no container chrome.
 *
 * Most grouping in this application is done with a label and whitespace rather
 * than a card. Cards are reserved for content that is genuinely a discrete
 * object — a case, an evidence item — so that when one appears it means
 * something.
 */
export function Section({ title, description, action, children, style }: SectionProps) {
  const theme = useTheme();
  return (
    <View style={[{ marginTop: theme.spacing.xxl }, style]}>
      {title || action ? (
        <View style={[styles.header, { marginBottom: theme.spacing.sm }]}>
          <View style={styles.headerText}>
            {title ? (
              <Text role="label" tone="tertiary">
                {title}
              </Text>
            ) : null}
            {description ? (
              <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xxs }}>
                {description}
              </Text>
            ) : null}
          </View>
          {action}
        </View>
      ) : null}
      {children}
    </View>
  );
}

interface PanelProps {
  children: ReactNode;
  /** `raised` for interactive rows and sheets, `sunken` for wells and code. */
  tone?: 'surface' | 'raised' | 'sunken' | 'accent' | 'positive' | 'caution' | 'critical';
  /** Adds internal padding. Off when the panel hosts its own rows. */
  padded?: boolean;
  level?: 'none' | 'low' | 'medium';
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/** A bordered surface. The only container that draws a box. */
export function Panel({
  children,
  tone = 'surface',
  padded = true,
  level = 'none',
  style,
  testID,
}: PanelProps) {
  const theme = useTheme();

  const tones = {
    surface: { background: theme.color.surface, border: theme.color.border },
    raised: { background: theme.color.surfaceRaised, border: theme.color.border },
    sunken: { background: theme.color.surfaceSunken, border: theme.color.border },
    accent: { background: theme.color.accentSubtle, border: theme.color.accentBorder },
    positive: { background: theme.color.positiveSubtle, border: theme.color.positiveBorder },
    caution: { background: theme.color.cautionSubtle, border: theme.color.cautionBorder },
    critical: { background: theme.color.criticalSubtle, border: theme.color.criticalBorder },
  }[tone];

  return (
    <View
      testID={testID}
      style={[
        {
          backgroundColor: tones.background,
          borderColor: tones.border,
          borderWidth: theme.borderWidth.thin,
          borderRadius: theme.radii.lg,
          padding: padded ? theme.spacing.lg : 0,
        },
        elevation(level, theme.scheme),
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** A hairline rule. Used between rows inside a panel, never as decoration. */
export function Divider({ inset = 0 }: { inset?: number }) {
  const theme = useTheme();
  return (
    <View
      style={{
        height: theme.borderWidth.thin,
        backgroundColor: theme.color.border,
        marginLeft: inset,
      }}
    />
  );
}

/** Vertical space between stacked elements, in grid units. */
export function Spacer({ size = 'lg' }: { size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'xxl' }) {
  const theme = useTheme();
  return <View style={{ height: theme.spacing[size] }} />;
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  headerText: { flex: 1, minWidth: 0 },
});
