import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';

const LOGO = require('../../../assets/brand-mark.png');

/**
 * The application's badge.
 *
 * The artwork carries its own wordmark and a two-line tagline, which sets a
 * floor on how small it can usefully be drawn: below roughly 64pt the tagline
 * is texture rather than text, and below 40pt the shield loses its detail. That
 * is why this takes a size rather than stretching to its container, and why
 * nothing places it in a header bar — a 24pt version of this badge would read
 * as a smudge.
 *
 * It is decorative by default. The screens that use it state the product name
 * in text alongside, so announcing the image as well would make a screen reader
 * say it twice.
 */
export interface BrandMarkProps {
  /** Rendered width and height, in points. Defaults to a comfortable 88. */
  size?: number;
  /**
   * Supplies an accessible name, for the rare placement with no adjacent text.
   * Left unset the badge is hidden from assistive technology.
   */
  label?: string;
  style?: StyleProp<ViewStyle>;
}

export function BrandMark({ size = 88, label, style }: BrandMarkProps) {
  return (
    <View
      style={[{ width: size, height: size }, style]}
      accessible={label !== undefined}
      accessibilityRole={label !== undefined ? 'image' : undefined}
      accessibilityLabel={label}
      importantForAccessibility={label === undefined ? 'no-hide-descendants' : 'yes'}
    >
      <Image
        source={LOGO}
        style={StyleSheet.absoluteFill}
        contentFit="contain"
        // The badge is a fixed asset, so there is nothing to fade in from and a
        // transition would read as a loading artefact on the sign-in screen.
        transition={0}
        accessible={false}
      />
    </View>
  );
}
