import React from 'react';
import { StyleSheet, View } from 'react-native';

import { Panel } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';

import type { Subsystem, SubsystemState } from '../useSystemStatus';

/**
 * The device readiness table.
 *
 * Laid out as a table rather than a grid of cards: an officer scans this
 * column-wise looking for the one row that is not ready, and a table makes that
 * scan fast. The state word carries the meaning; colour only reinforces it.
 */
export function SystemStatusPanel({ subsystems }: { subsystems: readonly Subsystem[] }) {
  const theme = useTheme();

  return (
    <Panel padded={false}>
      {subsystems.map((subsystem, index) => (
        <View
          key={subsystem.id}
          accessible
          accessibilityRole="text"
          accessibilityLabel={`${subsystem.label}. ${stateLabel(subsystem.state)}. ${subsystem.detail}`}
          style={[
            styles.row,
            {
              paddingVertical: theme.spacing.md,
              paddingHorizontal: theme.spacing.lg,
              borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
              borderTopColor: theme.color.border,
            },
          ]}
        >
          <View style={styles.labelColumn}>
            <Text role="body" accessible={false}>
              {subsystem.label}
            </Text>
            <Text role="caption" tone="tertiary" numberOfLines={1} accessible={false}>
              {subsystem.detail}
            </Text>
          </View>

          <View style={styles.stateColumn}>
            <Text
              role="monoSmall"
              weight="bold"
              style={{ color: stateColour(subsystem.state, theme.color) }}
              accessible={false}
            >
              {stateGlyph(subsystem.state)}
            </Text>
            <Text
              role="caption"
              weight="semibold"
              style={{ color: stateColour(subsystem.state, theme.color) }}
              accessible={false}
            >
              {stateLabel(subsystem.state)}
            </Text>
          </View>
        </View>
      ))}
    </Panel>
  );
}

function stateLabel(state: SubsystemState): string {
  return {
    READY: 'Ready',
    DEGRADED: 'Degraded',
    UNAVAILABLE: 'Unavailable',
    CHECKING: 'Checking',
  }[state];
}

function stateGlyph(state: SubsystemState): string {
  return { READY: '✓', DEGRADED: '!', UNAVAILABLE: '✕', CHECKING: '·' }[state];
}

function stateColour(
  state: SubsystemState,
  palette: { positive: string; caution: string; critical: string; textTertiary: string },
): string {
  return {
    READY: palette.positive,
    DEGRADED: palette.caution,
    UNAVAILABLE: palette.critical,
    CHECKING: palette.textTertiary,
  }[state];
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  labelColumn: { flex: 1, minWidth: 0 },
  stateColumn: { flexDirection: 'row', alignItems: 'center', gap: 6 },
});
