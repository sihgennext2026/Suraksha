import React, { type ReactNode } from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';

interface KeyValueRowProps {
  label: string;
  /** The value. Rendered monospaced when `mono` is set. */
  value: string;
  /** Monospace the value — for document numbers, references, codes. */
  mono?: boolean;
  /** Secondary line under the value. */
  hint?: string;
  /** Trailing content: a confidence bar, a badge, a chevron. */
  trailing?: ReactNode;
  onPress?: () => void;
  /** Stacks label above value. Use when values are long. */
  stacked?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * The workhorse row for displaying an extracted or recorded value.
 *
 * Two layouts: inline (label left, value right) for short values, and stacked
 * for anything that would wrap. Stacked is the right default for document data,
 * where a wrapped value is much harder to read back than a stacked one.
 */
export function KeyValueRow({
  label,
  value,
  mono = false,
  hint,
  trailing,
  onPress,
  stacked = false,
  style,
  testID,
}: KeyValueRowProps) {
  const theme = useTheme();

  const body = (
    <View
      style={[
        stacked ? styles.stacked : styles.inline,
        {
          paddingVertical: theme.spacing.md,
          paddingHorizontal: theme.spacing.lg,
          minHeight: theme.controlHeight.minTouchTarget,
        },
        style,
      ]}
    >
      <View style={stacked ? undefined : styles.labelInline}>
        <Text role={stacked ? 'label' : 'body'} tone={stacked ? 'tertiary' : 'secondary'}>
          {label}
        </Text>
      </View>

      <View style={stacked ? styles.stackedValue : styles.valueInline}>
        <Text
          role={mono ? 'mono' : 'body'}
          weight={mono ? undefined : 'medium'}
          align={stacked ? 'left' : 'right'}
          style={stacked ? { marginTop: theme.spacing.xs } : undefined}
        >
          {value}
        </Text>
        {hint ? (
          <Text
            role="caption"
            tone="tertiary"
            align={stacked ? 'left' : 'right'}
            style={{ marginTop: theme.spacing.xxs }}
          >
            {hint}
          </Text>
        ) : null}
      </View>

      {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
    </View>
  );

  if (!onPress) return body;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}, ${value}`}
      testID={testID}
      style={({ pressed }) => ({
        backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
      })}
    >
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  inline: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  stacked: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  labelInline: { flexShrink: 1 },
  valueInline: { flexShrink: 1, alignItems: 'flex-end' },
  stackedValue: { flex: 1, minWidth: 0 },
  trailing: { flexShrink: 0 },
});
