import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';

import { Text } from '@/components/primitives/Text';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';
import type { FaceQuality } from '@/contracts';

interface FaceSample {
  uri: string;
  label: string;
  quality: FaceQuality;
}

interface FaceComparisonProps {
  documentSample: FaceSample;
  liveSample: FaceSample;
}

/**
 * The two faces being compared, side by side.
 *
 * A similarity score is a claim; the officer still has to look. Placing both
 * images at equal size, on one row where the screen allows, is what makes the
 * comparison something a person can actually make rather than merely accept.
 */
export function FaceComparison({ documentSample, liveSample }: FaceComparisonProps) {
  const { canPairHorizontally } = useResponsive();

  return (
    <View style={[styles.row, !canPairHorizontally && styles.stacked]}>
      <FacePanel sample={documentSample} />
      <FacePanel sample={liveSample} />
    </View>
  );
}

function FacePanel({ sample }: { sample: FaceSample }) {
  const theme = useTheme();
  const { acceptable, metrics } = sample.quality;

  /**
   * The ArcFace pipeline reports quality as pass/fail gates plus raw
   * measurements — there is no 0..1 quality score, and manufacturing one from
   * the gates would be an invented confidence. So the gate is shown as a word
   * and the measurements are shown in their own units.
   */
  const qualityLabel =
    acceptable === null ? 'Not assessed' : acceptable ? 'Acceptable' : 'Below threshold';
  const qualityTone =
    acceptable === null
      ? theme.color.textTertiary
      : acceptable
        ? theme.color.positive
        : theme.color.caution;

  return (
    <View style={styles.panel}>
      <Text role="label" tone="tertiary" style={{ marginBottom: theme.spacing.sm }}>
        {sample.label}
      </Text>

      <View
        style={[
          styles.frame,
          {
            backgroundColor: theme.color.surfaceSunken,
            borderColor: theme.color.border,
            borderWidth: theme.borderWidth.thin,
            borderRadius: theme.radii.lg,
          },
        ]}
      >
        <Image
          source={{ uri: sample.uri }}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          transition={160}
          accessible
          accessibilityLabel={sample.label}
        />
      </View>

      <View style={[styles.qualityRow, { marginTop: theme.spacing.sm }]}>
        <Text role="caption" tone="secondary">
          Quality
        </Text>
        <Text role="caption" weight="semibold" style={{ color: qualityTone }}>
          {qualityLabel}
        </Text>
      </View>

      {metrics?.blur_score != null ? (
        <View style={styles.qualityRow}>
          <Text role="caption" tone="tertiary">
            Sharpness
          </Text>
          <Text role="monoSmall" tone="tertiary">
            {metrics.blur_score.toFixed(1)}
          </Text>
        </View>
      ) : null}

      {metrics?.brightness != null ? (
        <View style={styles.qualityRow}>
          <Text role="caption" tone="tertiary">
            Brightness
          </Text>
          <Text role="monoSmall" tone="tertiary">
            {metrics.brightness.toFixed(0)}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 16 },
  stacked: { flexDirection: 'column' },
  panel: { flex: 1, minWidth: 0 },
  frame: { width: '100%', aspectRatio: 0.82, overflow: 'hidden' },
  qualityRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
});
