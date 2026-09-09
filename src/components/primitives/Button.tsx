import React, { useCallback } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type PressableStateCallbackType,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import * as Haptics from 'expo-haptics';

import { useTheme } from '@/theme';

import { Text } from './Text';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'medium' | 'large';

export interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  loading?: boolean;
  /** Leading glyph. Kept to a single character so buttons stay compact. */
  glyph?: string;
  /** Fills the available width. Default for the primary action on a screen. */
  fullWidth?: boolean;
  /** Fires a light impact on press. Reserved for consequential actions. */
  haptic?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityHint?: string;
  testID?: string;
}

/**
 * One button component covering every variant.
 *
 * `PrimaryButton` and `SecondaryButton` are thin aliases below so call sites
 * read declaratively, but there is a single implementation of press state,
 * disabled state, loading state, and hit target sizing.
 */
export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'large',
  disabled = false,
  loading = false,
  glyph,
  fullWidth = false,
  haptic = false,
  style,
  accessibilityHint,
  testID,
}: ButtonProps) {
  const theme = useTheme();
  const inactive = disabled || loading;

  const handlePress = useCallback(() => {
    if (inactive) return;
    if (haptic) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onPress();
  }, [inactive, haptic, onPress]);

  const palette = {
    primary: {
      background: theme.color.accent,
      pressed: theme.color.accentPressed,
      border: theme.color.accent,
      text: theme.color.textOnAccent,
    },
    secondary: {
      background: theme.color.surfaceRaised,
      pressed: theme.color.surfaceSunken,
      border: theme.color.borderStrong,
      text: theme.color.textPrimary,
    },
    ghost: {
      background: 'transparent',
      pressed: theme.color.surfaceSunken,
      border: 'transparent',
      text: theme.color.accent,
    },
    danger: {
      background: theme.color.critical,
      pressed: theme.color.criticalPressed,
      border: theme.color.critical,
      text: theme.color.textOnAccent,
    },
  }[variant];

  const height = size === 'large' ? theme.controlHeight.large : theme.controlHeight.medium;

  const containerStyle = useCallback(
    ({ pressed }: PressableStateCallbackType): StyleProp<ViewStyle> => [
      styles.base,
      {
        height,
        paddingHorizontal: size === 'large' ? theme.spacing.xxl : theme.spacing.lg,
        borderRadius: theme.radii.md,
        borderWidth: theme.borderWidth.thin,
        backgroundColor: pressed ? palette.pressed : palette.background,
        borderColor: palette.border,
        opacity: inactive ? theme.opacity.disabled : 1,
        alignSelf: fullWidth ? 'stretch' : 'flex-start',
      },
      style,
    ],
    [height, size, theme, palette, inactive, fullWidth, style],
  );

  return (
    <Pressable
      onPress={handlePress}
      disabled={inactive}
      style={containerStyle}
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: loading }}
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      testID={testID}
    >
      {loading ? (
        <ActivityIndicator size="small" color={palette.text} />
      ) : (
        <View style={styles.content}>
          {glyph ? (
            <Text
              role="body"
              weight="bold"
              style={[styles.glyph, { color: palette.text }]}
              accessible={false}
            >
              {glyph}
            </Text>
          ) : null}
          <Text
            role="body"
            weight="semibold"
            style={{ color: palette.text }}
            numberOfLines={1}
            accessible={false}
          >
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  glyph: {
    fontSize: 15,
  },
});

export function PrimaryButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button {...props} variant="primary" />;
}

export function SecondaryButton(props: Omit<ButtonProps, 'variant'>) {
  return <Button {...props} variant="secondary" />;
}
