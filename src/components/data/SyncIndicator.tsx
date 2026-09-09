import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';

interface SyncIndicatorProps {
  online: boolean;
  /** Cases waiting to upload. Zero hides the count. */
  pending: number;
  syncing: boolean;
  onPress?: () => void;
  /** Compact form for headers; full form for the dashboard. */
  compact?: boolean;
}

/**
 * Connectivity and outbox state, together.
 *
 * These two facts belong in one control: "offline" alone does not tell an
 * officer whether anything is at risk, and "4 pending" alone does not tell them
 * why. Shown together they answer the only question that matters in the field —
 * is my work safe, and is it off the device yet.
 */
export function SyncIndicator({
  online,
  pending,
  syncing,
  onPress,
  compact = true,
}: SyncIndicatorProps) {
  const theme = useTheme();

  const tone = syncing
    ? theme.color.info
    : !online
      ? theme.color.caution
      : pending > 0
        ? theme.color.caution
        : theme.color.positive;

  const glyph = syncing ? '⟳' : online ? '●' : '○';
  const networkLabel = online ? 'Online' : 'Offline';
  const stateLabel = syncing
    ? 'Syncing'
    : pending > 0
      ? `${pending} pending`
      : online
        ? 'All synced'
        : 'Nothing pending';

  const accessibilityLabel = `Network ${networkLabel.toLowerCase()}. ${
    syncing
      ? 'Synchronising now'
      : pending > 0
        ? `${pending} ${pending === 1 ? 'case' : 'cases'} pending synchronisation`
        : 'Nothing pending synchronisation'
  }`;

  const body = (
    <View
      style={[
        styles.container,
        {
          borderColor: theme.color.border,
          borderWidth: theme.borderWidth.thin,
          borderRadius: theme.radii.sm,
          backgroundColor: theme.color.surfaceSunken,
          paddingHorizontal: theme.spacing.sm,
          paddingVertical: compact ? 3 : theme.spacing.xs,
          gap: theme.spacing.xs,
        },
      ]}
    >
      <Text role="monoSmall" style={{ color: tone, fontSize: 10 }} accessible={false}>
        {glyph}
      </Text>
      <Text role="monoSmall" tone="secondary" style={{ fontSize: 10 }} accessible={false}>
        {compact
          ? pending > 0
            ? `${networkLabel} · ${pending}`
            : networkLabel
          : `${networkLabel} · ${stateLabel}`}
      </Text>
    </View>
  );

  if (!onPress) {
    return (
      <View accessible accessibilityRole="text" accessibilityLabel={accessibilityLabel}>
        {body}
      </View>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint="Opens synchronisation details"
      hitSlop={8}
      style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start' },
});
