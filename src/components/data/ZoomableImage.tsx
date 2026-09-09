import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';
import { clamp } from '@/utils/array';

interface ZoomableImageProps {
  uri: string;
  aspectRatio?: number;
  /** Maximum magnification. Three is enough to read microtext on a capture. */
  maxScale?: number;
  accessibilityLabel?: string;
}

const MIN_SCALE = 1;

/**
 * Pinch-and-pan inspection of a capture.
 *
 * Document review is where an officer decides whether the image is good enough
 * to screen, which they cannot do without getting close to it. Double-tap
 * returns to fit, so there is always a way back to the whole document.
 */
export function ZoomableImage({
  uri,
  aspectRatio = 1.42,
  maxScale = 3,
  accessibilityLabel = 'Captured document, pinch to zoom',
}: ZoomableImageProps) {
  const theme = useTheme();

  const scale = useSharedValue(MIN_SCALE);
  const savedScale = useSharedValue(MIN_SCALE);
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);
  const savedTranslateX = useSharedValue(0);
  const savedTranslateY = useSharedValue(0);

  const pinch = Gesture.Pinch()
    .onUpdate((event) => {
      scale.value = clamp(savedScale.value * event.scale, MIN_SCALE, maxScale);
    })
    .onEnd(() => {
      savedScale.value = scale.value;
      if (scale.value <= MIN_SCALE) {
        translateX.value = withTiming(0);
        translateY.value = withTiming(0);
        savedTranslateX.value = 0;
        savedTranslateY.value = 0;
      }
    });

  const pan = Gesture.Pan()
    .averageTouches(true)
    .onUpdate((event) => {
      if (scale.value <= MIN_SCALE) return;
      // Travel is bounded by how much of the image sits outside the frame, so
      // the document can never be dragged completely off screen.
      const limit = 140 * (scale.value - 1);
      translateX.value = clamp(savedTranslateX.value + event.translationX, -limit, limit);
      translateY.value = clamp(savedTranslateY.value + event.translationY, -limit, limit);
    })
    .onEnd(() => {
      savedTranslateX.value = translateX.value;
      savedTranslateY.value = translateY.value;
    });

  const doubleTap = Gesture.Tap()
    .numberOfTaps(2)
    .onEnd(() => {
      const next = scale.value > MIN_SCALE ? MIN_SCALE : 2;
      scale.value = withTiming(next, { duration: theme.duration.normal });
      savedScale.value = next;
      if (next === MIN_SCALE) {
        translateX.value = withTiming(0, { duration: theme.duration.normal });
        translateY.value = withTiming(0, { duration: theme.duration.normal });
        savedTranslateX.value = 0;
        savedTranslateY.value = 0;
      }
    });

  const composed = Gesture.Simultaneous(pinch, pan, doubleTap);

  const imageStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { translateY: translateY.value },
      { scale: scale.value },
    ],
  }));

  return (
    <View>
      <GestureDetector gesture={composed}>
        <View
          style={[
            styles.frame,
            {
              aspectRatio,
              backgroundColor: theme.color.surfaceSunken,
              borderColor: theme.color.border,
              borderWidth: theme.borderWidth.thin,
              borderRadius: theme.radii.lg,
            },
          ]}
        >
          <Animated.View style={[StyleSheet.absoluteFill, imageStyle]}>
            <Image
              source={{ uri }}
              style={StyleSheet.absoluteFill}
              contentFit="contain"
              transition={160}
              accessible
              accessibilityLabel={accessibilityLabel}
            />
          </Animated.View>
        </View>
      </GestureDetector>

      <Text role="caption" tone="tertiary" align="center" style={{ marginTop: theme.spacing.sm }}>
        Pinch to zoom · double tap to fit
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { width: '100%', overflow: 'hidden' },
});
