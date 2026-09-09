import React, { type ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';

interface ScreenProps {
  children: ReactNode;
  /** Wraps content in a scroll view. Off for full-bleed screens like capture. */
  scroll?: boolean;
  /** Pull-to-refresh. Only meaningful with `scroll`. */
  onRefresh?: () => void;
  refreshing?: boolean;
  /** Removes the default horizontal padding for edge-to-edge content. */
  bleed?: boolean;
  /** Content pinned to the bottom, outside the scroll area. */
  footer?: ReactNode;
  /** Applies the canvas colour rather than the default surface colour. */
  tone?: 'canvas' | 'surface' | 'inverse';
  style?: StyleProp<ViewStyle>;
  contentStyle?: StyleProp<ViewStyle>;
  testID?: string;
}

/**
 * Every screen's outer container.
 *
 * It owns safe areas, the reading-measure constraint on tablets, keyboard
 * avoidance, and the footer action bar. Centralising this is what keeps padding
 * and safe-area handling identical everywhere rather than re-derived per screen.
 */
export function Screen({
  children,
  scroll = true,
  onRefresh,
  refreshing = false,
  bleed = false,
  footer,
  tone = 'canvas',
  style,
  contentStyle,
  testID,
}: ScreenProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { contentMaxWidth, isTablet } = useResponsive();

  const background =
    tone === 'canvas'
      ? theme.color.canvas
      : tone === 'surface'
        ? theme.color.surface
        : theme.color.surfaceInverse;

  const horizontalPadding = bleed ? 0 : theme.spacing.lg;

  const inner = (
    <View
      style={[
        styles.measure,
        isTablet && !bleed ? { maxWidth: contentMaxWidth, alignSelf: 'center' } : null,
      ]}
    >
      {children}
    </View>
  );

  return (
    <View style={[styles.root, { backgroundColor: background }, style]} testID={testID}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.top}
      >
        {scroll ? (
          <ScrollView
            style={styles.root}
            contentContainerStyle={[
              {
                paddingHorizontal: horizontalPadding,
                paddingBottom: footer ? theme.spacing.lg : insets.bottom + theme.spacing.xxxl,
              },
              contentStyle,
            ]}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            refreshControl={
              onRefresh ? (
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                  tintColor={theme.color.textSecondary}
                  colors={[theme.color.accent]}
                  progressBackgroundColor={theme.color.surface}
                />
              ) : undefined
            }
          >
            {inner}
          </ScrollView>
        ) : (
          <View style={[styles.root, { paddingHorizontal: horizontalPadding }, contentStyle]}>
            {inner}
          </View>
        )}

        {footer ? (
          <View
            style={[
              styles.footer,
              {
                paddingHorizontal: theme.spacing.lg,
                paddingTop: theme.spacing.md,
                paddingBottom: insets.bottom + theme.spacing.md,
                backgroundColor: theme.color.surface,
                borderTopColor: theme.color.border,
                borderTopWidth: theme.borderWidth.thin,
              },
            ]}
          >
            <View
              style={
                isTablet ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : null
              }
            >
              {footer}
            </View>
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  measure: { width: '100%' },
  footer: { width: '100%' },
});
