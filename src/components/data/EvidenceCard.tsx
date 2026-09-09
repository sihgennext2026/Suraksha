import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { SEVERITY_PRESENTATION } from '@/constants/labels';
import { useTheme } from '@/theme';
import type { EvidenceItem } from '@/contracts';

interface EvidenceCardProps {
  item: EvidenceItem;
  onPress?: () => void;
  /** Hides the chevron when the row has no detail screen behind it. */
  navigable?: boolean;
}

/**
 * One line of the evidence index.
 *
 * The index is built by the backend — this component renders it and derives
 * nothing. Both the module status and the severity are shown, because they
 * answer different questions: whether the check ran at all, and whether it found
 * anything. A module that did not run is drawn in neutral tones, never in the
 * colour of a failure.
 */
function EvidenceCardComponent({ item, onPress, navigable = true }: EvidenceCardProps) {
  const theme = useTheme();

  const ran = item.status === 'SUCCESS' || item.status === 'PARTIAL';
  const presentation = SEVERITY_PRESENTATION[item.severity];

  const tone = !ran
    ? theme.color.neutral
    : {
        NONE: theme.color.positive,
        LOW: theme.color.info,
        MEDIUM: theme.color.caution,
        HIGH: theme.color.critical,
      }[item.severity];

  const glyph = ran ? presentation.glyph : '–';
  const announcement = ran
    ? `${item.headline}. ${presentation.a11yLabel}. ${item.detail}`
    : `${item.headline}. This check did not run. ${item.detail}`;

  const content = (
    <View
      style={[
        styles.row,
        {
          paddingVertical: theme.spacing.md,
          paddingHorizontal: theme.spacing.lg,
          minHeight: theme.controlHeight.minTouchTarget,
        },
      ]}
    >
      <View style={[styles.marker, { backgroundColor: tone, borderRadius: theme.radii.xs }]}>
        <Text
          role="monoSmall"
          weight="bold"
          style={{ color: theme.color.textOnAccent, fontSize: 10 }}
          accessible={false}
        >
          {glyph}
        </Text>
      </View>

      <View style={styles.body}>
        <Text role="body" weight="medium" accessible={false}>
          {item.headline}
        </Text>
        <Text
          role="caption"
          tone={ran ? 'secondary' : 'tertiary'}
          style={{ marginTop: 1 }}
          accessible={false}
        >
          {item.detail}
        </Text>
      </View>

      {onPress && navigable ? (
        <Text role="body" tone="tertiary" accessible={false}>
          ›
        </Text>
      ) : null}
    </View>
  );

  if (!onPress) {
    return (
      <View accessible accessibilityRole="text" accessibilityLabel={announcement}>
        {content}
      </View>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={announcement}
      accessibilityHint="Opens the full findings for this check"
      style={({ pressed }) => ({
        backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
      })}
    >
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  marker: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1, minWidth: 0 },
});

export const EvidenceCard = memo(EvidenceCardComponent);
