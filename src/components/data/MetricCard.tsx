import React, { type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Panel } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';

interface MetricCardProps {
  label: string;
  value: string;
  /** Short qualifier under the value, e.g. `of 100` or `since 09:00`. */
  caption?: string;
  tone?: 'neutral' | 'positive' | 'caution' | 'critical' | 'accent';
  onPress?: () => void;
  trailing?: ReactNode;
  testID?: string;
}

/**
 * A single operational figure.
 *
 * Used on the dashboard where a count needs to be readable at arm's length. The
 * value is set in tabular figures so a row of cards does not jitter as counts
 * change.
 */
export function MetricCard({
  label,
  value,
  caption,
  tone = 'neutral',
  onPress,
  trailing,
  testID,
}: MetricCardProps) {
  const theme = useTheme();

  const valueColour = {
    neutral: theme.color.textPrimary,
    positive: theme.color.positive,
    caution: theme.color.caution,
    critical: theme.color.critical,
    accent: theme.color.accent,
  }[tone];

  const content = (
    <Panel style={styles.panel} level="low">
      <View style={styles.header}>
        <Text role="label" tone="tertiary" numberOfLines={1} style={styles.label}>
          {label}
        </Text>
        {trailing}
      </View>
      <Text
        role="title"
        style={[styles.value, { color: valueColour, marginTop: theme.spacing.sm }]}
        numberOfLines={1}
      >
        {value}
      </Text>
      {caption ? (
        <Text role="caption" tone="tertiary" numberOfLines={1} style={{ marginTop: 2 }}>
          {caption}
        </Text>
      ) : null}
    </Panel>
  );

  if (!onPress) return content;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}, ${value}${caption ? `, ${caption}` : ''}`}
      testID={testID}
      style={({ pressed }) => [styles.pressable, { opacity: pressed ? 0.75 : 1 }]}
    >
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressable: { flex: 1 },
  panel: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  label: { flexShrink: 1 },
  value: { fontVariant: ['tabular-nums'] },
});
