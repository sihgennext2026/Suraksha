import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { FadeIn, FadeOut } from 'react-native-reanimated';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';

/**
 * Capture chrome: the positioning guide, the live status read-out, and the
 * controls.
 *
 * The guiding principle is that the officer should never have to guess what is
 * wrong. Every negative state names the problem and the correction — "move the
 * document into the frame", not "cannot capture".
 */

export type CaptureFeedbackTone = 'ready' | 'adjusting' | 'blocked';

interface CaptureFrameProps {
  /** Guide aspect ratio, width over height. */
  aspectRatio: number;
  /** Fraction of the screen width the guide occupies. */
  widthFraction?: number;
  tone: CaptureFeedbackTone;
  /** Circular guide for face capture rather than a rectangle. */
  shape?: 'rectangle' | 'oval';
}

export function CaptureFrame({
  aspectRatio,
  widthFraction = 0.88,
  tone,
  shape = 'rectangle',
}: CaptureFrameProps) {
  const theme = useTheme();

  const colour = {
    ready: theme.color.positive,
    adjusting: theme.color.caution,
    blocked: theme.color.critical,
  }[tone];

  return (
    <View style={styles.frameLayer} pointerEvents="none">
      <View
        style={[
          styles.guide,
          {
            width: `${widthFraction * 100}%`,
            aspectRatio,
            borderRadius: shape === 'oval' ? 9999 : theme.radii.md,
            borderWidth: shape === 'oval' ? theme.borderWidth.medium : 0,
            borderColor: shape === 'oval' ? colour : 'transparent',
          },
        ]}
      >
        {shape === 'rectangle'
          ? (['topLeft', 'topRight', 'bottomLeft', 'bottomRight'] as const).map((corner) => (
              <View key={corner} style={[styles.corner, cornerStyles[corner]]}>
                <View
                  style={{
                    position: 'absolute',
                    width: 26,
                    height: theme.borderWidth.heavy,
                    backgroundColor: colour,
                    ...horizontalCornerPosition[corner],
                  }}
                />
                <View
                  style={{
                    position: 'absolute',
                    width: theme.borderWidth.heavy,
                    height: 26,
                    backgroundColor: colour,
                    ...verticalCornerPosition[corner],
                  }}
                />
              </View>
            ))
          : null}
      </View>
    </View>
  );
}

interface CaptureStatusProps {
  tone: CaptureFeedbackTone;
  /** Primary state, e.g. `DOCUMENT DETECTED`. */
  headline: string;
  /** What to do next, e.g. `Hold steady and capture`. */
  instruction: string;
  /** Individual checks shown as a compact list. */
  checks?: { label: string; ok: boolean }[];
}

export function CaptureStatus({ tone, headline, instruction, checks }: CaptureStatusProps) {
  const theme = useTheme();

  const colour = {
    ready: theme.color.positive,
    adjusting: theme.color.caution,
    blocked: theme.color.critical,
  }[tone];

  const glyph = { ready: '✓', adjusting: '!', blocked: '✕' }[tone];

  return (
    <Animated.View
      entering={FadeIn.duration(theme.duration.fast)}
      exiting={FadeOut.duration(theme.duration.fast)}
      style={[
        styles.status,
        {
          backgroundColor: 'rgba(8, 13, 19, 0.82)',
          borderColor: colour,
          borderWidth: theme.borderWidth.thin,
          borderRadius: theme.radii.md,
          padding: theme.spacing.md,
        },
      ]}
      accessible
      accessibilityRole="text"
      accessibilityLiveRegion="polite"
      accessibilityLabel={`${headline}. ${instruction}`}
    >
      <View style={styles.statusHead}>
        <Text role="monoSmall" weight="bold" style={{ color: colour }} accessible={false}>
          {glyph}
        </Text>
        <Text role="label" style={{ color: colour }} accessible={false}>
          {headline}
        </Text>
      </View>
      <Text
        role="caption"
        style={{ color: '#D8E1EB', marginTop: theme.spacing.xs }}
        accessible={false}
      >
        {instruction}
      </Text>

      {checks && checks.length > 0 ? (
        <View style={[styles.checks, { marginTop: theme.spacing.sm }]}>
          {checks.map((check) => (
            <View key={check.label} style={styles.checkRow}>
              <Text
                role="monoSmall"
                style={{ color: check.ok ? theme.color.positive : theme.color.caution }}
                accessible={false}
              >
                {check.ok ? '✓' : '○'}
              </Text>
              <Text role="monoSmall" style={{ color: '#9FB0C2' }} accessible={false}>
                {check.label}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </Animated.View>
  );
}

interface CaptureControlsProps {
  onCapture: () => void;
  captureDisabled?: boolean;
  busy?: boolean;
  /** Left-hand auxiliary control, typically flash. */
  leftControl?: React.ReactNode;
  /** Right-hand auxiliary control, typically import or camera flip. */
  rightControl?: React.ReactNode;
  captureLabel?: string;
}

export function CaptureControls({
  onCapture,
  captureDisabled = false,
  busy = false,
  leftControl,
  rightControl,
  captureLabel = 'Capture',
}: CaptureControlsProps) {
  const theme = useTheme();

  return (
    <View style={styles.controls}>
      <View style={styles.controlSlot}>{leftControl}</View>

      <Pressable
        onPress={onCapture}
        disabled={captureDisabled || busy}
        accessibilityRole="button"
        accessibilityLabel={captureLabel}
        accessibilityState={{ disabled: captureDisabled || busy, busy }}
        style={({ pressed }) => [
          styles.shutterOuter,
          {
            borderColor: '#FFFFFF',
            borderWidth: theme.borderWidth.thick,
            opacity: captureDisabled ? 0.4 : 1,
            transform: [{ scale: pressed ? 0.94 : 1 }],
          },
        ]}
      >
        <View
          style={[styles.shutterInner, { backgroundColor: busy ? theme.color.accent : '#FFFFFF' }]}
        />
      </Pressable>

      <View style={styles.controlSlot}>{rightControl}</View>
    </View>
  );
}

interface CaptureToggleProps {
  label: string;
  glyph: string;
  active?: boolean;
  onPress: () => void;
  accessibilityLabel: string;
}

export function CaptureToggle({
  label,
  glyph,
  active = false,
  onPress,
  accessibilityLabel,
}: CaptureToggleProps) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.toggle,
        {
          borderRadius: theme.radii.md,
          backgroundColor: active
            ? 'rgba(59, 130, 246, 0.28)'
            : pressed
              ? 'rgba(255,255,255,0.16)'
              : 'rgba(255,255,255,0.08)',
          borderColor: active ? theme.color.accent : 'rgba(255,255,255,0.2)',
          borderWidth: theme.borderWidth.thin,
        },
      ]}
    >
      <Text role="body" style={{ color: '#FFFFFF' }} accessible={false}>
        {glyph}
      </Text>
      <Text role="monoSmall" style={{ color: '#C8D3DE', fontSize: 9 }} accessible={false}>
        {label}
      </Text>
    </Pressable>
  );
}

const cornerStyles = StyleSheet.create({
  topLeft: { top: -2, left: -2 },
  topRight: { top: -2, right: -2 },
  bottomLeft: { bottom: -2, left: -2 },
  bottomRight: { bottom: -2, right: -2 },
});

const horizontalCornerPosition = {
  topLeft: { top: 0, left: 0 },
  topRight: { top: 0, right: 0 },
  bottomLeft: { bottom: 0, left: 0 },
  bottomRight: { bottom: 0, right: 0 },
} as const;

const verticalCornerPosition = {
  topLeft: { top: 0, left: 0 },
  topRight: { top: 0, right: 0 },
  bottomLeft: { bottom: 0, left: 0 },
  bottomRight: { bottom: 0, right: 0 },
} as const;

const styles = StyleSheet.create({
  frameLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  guide: { position: 'relative' },
  corner: { position: 'absolute', width: 26, height: 26 },
  status: { alignSelf: 'stretch' },
  statusHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checks: { gap: 3 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
  },
  controlSlot: { width: 64, alignItems: 'center' },
  shutterOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterInner: { width: 56, height: 56, borderRadius: 28 },
  toggle: {
    width: 52,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 1,
  },
});
