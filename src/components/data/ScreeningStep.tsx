import React, { memo, useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { Text } from '@/components/primitives/Text';
import { STAGE_STATUS_PRESENTATION } from '@/constants/labels';
import { SCREENING_STAGE_DESCRIPTORS } from '@/constants/screening';
import { useTheme } from '@/theme';
import type { ScreeningStageState } from '@/types';

interface ScreeningStepProps {
  stage: ScreeningStageState;
  /** Draws the connector down to the next step. Omitted on the last row. */
  connected: boolean;
}

/**
 * One row of the screening pipeline.
 *
 * The status glyph and the label carry the state; the animation only draws the
 * eye to the stage that is currently running. A stage that has settled is
 * completely static, so a glance at the list tells the officer where the run is
 * without anything moving to distract from the findings.
 */
function ScreeningStepComponent({ stage, connected }: ScreeningStepProps) {
  const theme = useTheme();
  const descriptor = SCREENING_STAGE_DESCRIPTORS[stage.id];
  const presentation = STAGE_STATUS_PRESENTATION[stage.status];

  const pulse = useSharedValue(1);
  const isProcessing = stage.status === 'PROCESSING';

  useEffect(() => {
    if (isProcessing) {
      pulse.value = withRepeat(
        withSequence(
          withTiming(0.35, { duration: 620, easing: Easing.inOut(Easing.quad) }),
          withTiming(1, { duration: 620, easing: Easing.inOut(Easing.quad) }),
        ),
        -1,
        false,
      );
    } else {
      cancelAnimation(pulse);
      pulse.value = withTiming(1, { duration: theme.duration.fast });
    }
    return () => cancelAnimation(pulse);
  }, [isProcessing, pulse, theme.duration.fast]);

  const pulseStyle = useAnimatedStyle(() => ({ opacity: pulse.value }));

  const tone = {
    WAITING: theme.color.textTertiary,
    PROCESSING: theme.color.accent,
    COMPLETED: theme.color.positive,
    WARNING: theme.color.caution,
    // A stage that did not run is neutral, never red: it is an absence of
    // evidence, not a finding against the document.
    FAILED: theme.color.neutral,
    NOT_AVAILABLE: theme.color.neutral,
  }[stage.status];

  const settled = stage.status !== 'WAITING' && stage.status !== 'PROCESSING';

  return (
    <View
      style={styles.row}
      accessible
      accessibilityRole="text"
      accessibilityLabel={`${descriptor.label}. ${presentation.a11yLabel}${
        stage.detail ? `. ${stage.detail}` : ''
      }${stage.error ? `. ${stage.error}` : ''}`}
    >
      <View style={styles.gutter}>
        <Animated.View
          style={[
            styles.marker,
            {
              borderColor: tone,
              borderWidth: theme.borderWidth.medium,
              borderRadius: theme.radii.pill,
              backgroundColor: settled ? tone : 'transparent',
            },
            isProcessing ? pulseStyle : null,
          ]}
        >
          {settled ? (
            <Text
              role="monoSmall"
              weight="bold"
              style={{ color: theme.color.textOnAccent, fontSize: 10 }}
              accessible={false}
            >
              {presentation.glyph}
            </Text>
          ) : isProcessing ? (
            <View
              style={{
                width: 6,
                height: 6,
                borderRadius: theme.radii.pill,
                backgroundColor: tone,
              }}
            />
          ) : null}
        </Animated.View>

        {connected ? (
          <View
            style={[
              styles.connector,
              {
                backgroundColor: settled ? theme.color.border : theme.color.border,
                width: theme.borderWidth.medium,
              },
            ]}
          />
        ) : null}
      </View>

      <View style={[styles.body, { paddingBottom: connected ? theme.spacing.xl : 0 }]}>
        <View style={styles.titleRow}>
          <Text
            role="body"
            weight={isProcessing ? 'semibold' : 'medium'}
            tone={stage.status === 'WAITING' ? 'tertiary' : 'primary'}
            accessible={false}
          >
            {descriptor.label}
          </Text>
          <Text role="monoSmall" tone="tertiary" accessible={false}>
            {descriptor.engine}
          </Text>
        </View>

        <Text
          role="caption"
          tone={stage.status === 'WAITING' ? 'tertiary' : 'secondary'}
          style={{ marginTop: 2 }}
          accessible={false}
        >
          {stage.error ?? stage.detail ?? descriptor.description}
        </Text>

        {isProcessing ? (
          <View
            style={[
              styles.track,
              { backgroundColor: theme.color.neutralSubtle, marginTop: theme.spacing.sm },
            ]}
          >
            <View
              style={{
                width: `${Math.round(stage.progress * 100)}%`,
                height: '100%',
                backgroundColor: theme.color.accent,
              }}
            />
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12 },
  gutter: { alignItems: 'center', width: 18 },
  marker: { width: 18, height: 18, alignItems: 'center', justifyContent: 'center' },
  connector: { flex: 1, marginVertical: 4 },
  body: { flex: 1, minWidth: 0 },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  track: { height: 3, borderRadius: 2, overflow: 'hidden' },
});

export const ScreeningStep = memo(ScreeningStepComponent);
