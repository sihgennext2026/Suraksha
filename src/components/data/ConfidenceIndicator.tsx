import React from 'react';
import { StyleSheet, View } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';
import { formatPercent } from '@/utils/format';
import { clamp } from '@/utils/array';

interface ConfidenceIndicatorProps {
  /** 0..1. */
  value: number;
  /** Width of the track. Rows use a fixed width so bars align down a column. */
  width?: number;
  /** Shows the percentage beside the bar. */
  showValue?: boolean;
  /** Inverts the tone ramp, for scores where high means bad. */
  invert?: boolean;
  label?: string;
}

/**
 * A compact confidence bar.
 *
 * Bars in a column all use the same track width so an officer can compare field
 * confidences by eye without reading every number. The tone ramp is a secondary
 * cue only — the percentage is always available as text.
 */
export function ConfidenceIndicator({
  value,
  width = 56,
  showValue = true,
  invert = false,
  label,
}: ConfidenceIndicatorProps) {
  const theme = useTheme();
  const clamped = clamp(value, 0, 1);
  const effective = invert ? 1 - clamped : clamped;

  const colour =
    effective >= 0.9
      ? theme.color.positive
      : effective >= 0.75
        ? theme.color.info
        : effective >= 0.5
          ? theme.color.caution
          : theme.color.critical;

  return (
    <View
      style={styles.row}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={label ? `${label}, ${formatPercent(clamped)}` : formatPercent(clamped)}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped * 100) }}
    >
      <View
        style={{
          width,
          height: 4,
          borderRadius: theme.radii.xs,
          backgroundColor: theme.color.neutralSubtle,
          overflow: 'hidden',
        }}
      >
        <View
          style={{
            width: `${clamped * 100}%`,
            height: '100%',
            backgroundColor: colour,
          }}
        />
      </View>
      {showValue ? (
        <Text role="monoSmall" tone="secondary" style={styles.value}>
          {formatPercent(clamped)}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  value: { minWidth: 34, textAlign: 'right' },
});
