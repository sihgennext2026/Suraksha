import React, { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';
import type { RiskLevel } from '@/types';
import { clamp } from '@/utils/array';

interface RiskMeterProps {
  /** Normalised 0..1, as produced by the fusion engine. */
  score: number;
  level: RiskLevel;
  bands: { review_at_or_above: number; high_at_or_above: number };
  /** Animates the marker in. Off when re-entering a completed case. */
  animate?: boolean;
}

/**
 * The risk score, shown against the bands that produced it.
 *
 * Showing a bare number invites the question "out of what, and where is the
 * line?". Drawing the score against its bands answers both, and makes it
 * obvious when a result sits just inside a boundary — which is exactly when an
 * officer should weigh their own observation most heavily.
 */
export function RiskMeter({ score, level, bands, animate = true }: RiskMeterProps) {
  const theme = useTheme();
  const clamped = clamp(score, 0, 1);
  const progress = useSharedValue(animate ? 0 : clamped);

  useEffect(() => {
    if (!animate) {
      progress.value = clamped;
      return;
    }
    progress.value = withTiming(clamped, {
      duration: theme.duration.deliberate,
      easing: Easing.out(Easing.cubic),
    });
  }, [clamped, animate, progress, theme.duration.deliberate]);

  const markerStyle = useAnimatedStyle(() => ({ left: `${progress.value * 100}%` }));

  const levelColour = {
    LOW: theme.color.positive,
    REVIEW: theme.color.caution,
    HIGH: theme.color.critical,
  }[level];

  const lowWidth = bands.review_at_or_above;
  const reviewWidth = bands.high_at_or_above - bands.review_at_or_above;
  const highWidth = 1 - bands.high_at_or_above;

  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={`Fused risk score ${clamped.toFixed(2)} of 1.00`}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped * 100) }}
    >
      <View style={[styles.track, { borderRadius: theme.radii.xs }]}>
        <View style={{ flex: lowWidth, backgroundColor: theme.color.positiveSubtle }} />
        <View style={{ flex: reviewWidth, backgroundColor: theme.color.cautionSubtle }} />
        <View style={{ flex: highWidth, backgroundColor: theme.color.criticalSubtle }} />

        <Animated.View style={[styles.marker, markerStyle]}>
          <View
            style={{
              width: 3,
              height: 20,
              marginLeft: -1.5,
              borderRadius: theme.radii.xs,
              backgroundColor: levelColour,
            }}
          />
        </Animated.View>
      </View>

      <View style={[styles.scale, { marginTop: theme.spacing.xs }]}>
        <Text role="monoSmall" tone="tertiary">
          0.00
        </Text>
        <Text
          role="monoSmall"
          tone="tertiary"
          style={{ position: 'absolute', left: `${bands.review_at_or_above * 100}%` }}
        >
          {bands.review_at_or_above.toFixed(2)}
        </Text>
        <Text
          role="monoSmall"
          tone="tertiary"
          style={{ position: 'absolute', left: `${bands.high_at_or_above * 100}%` }}
        >
          {bands.high_at_or_above.toFixed(2)}
        </Text>
        <Text role="monoSmall" tone="tertiary">
          1.00
        </Text>
      </View>

      <View style={[styles.legend, { marginTop: theme.spacing.sm }]}>
        <Text role="caption" tone="tertiary">
          Below {bands.review_at_or_above.toFixed(2)} low · {bands.review_at_or_above.toFixed(2)}{' '}
          to {bands.high_at_or_above.toFixed(2)} review · {bands.high_at_or_above.toFixed(2)} and
          above high
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  track: { flexDirection: 'row', height: 10, overflow: 'visible' },
  marker: { position: 'absolute', top: -5, bottom: -5, justifyContent: 'center' },
  scale: { flexDirection: 'row', justifyContent: 'space-between', position: 'relative' },
  legend: {},
});
