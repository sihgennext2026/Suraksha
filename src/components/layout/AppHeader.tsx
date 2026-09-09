import React, { type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Text } from '@/components/primitives/Text';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';

interface AppHeaderProps {
  title: string;
  subtitle?: string;
  /** Micro-label above the title, e.g. `STEP 2 OF 5`. */
  eyebrow?: string;
  onBack?: () => void;
  /** Label announced for the back control, e.g. `Back to document capture`. */
  backLabel?: string;
  /** Trailing controls: sync state, a single action. Keep to one or two items. */
  right?: ReactNode;
  /** Removes the bottom border where the screen supplies its own separator. */
  borderless?: boolean;
}

/**
 * The application header.
 *
 * Deliberately flat: no large title collapse, no blur, no elevation. It states
 * where the officer is and offers at most one way back, which is the behaviour a
 * multi-step evidence workflow needs.
 */
export function AppHeader({
  title,
  subtitle,
  eyebrow,
  onBack,
  backLabel,
  right,
  borderless = false,
}: AppHeaderProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { contentMaxWidth, isTablet } = useResponsive();

  return (
    <View
      style={[
        {
          paddingTop: insets.top + theme.spacing.sm,
          paddingBottom: theme.spacing.md,
          paddingHorizontal: theme.spacing.lg,
          backgroundColor: theme.color.surface,
          borderBottomWidth: borderless ? 0 : theme.borderWidth.thin,
          borderBottomColor: theme.color.border,
        },
      ]}
    >
      <View
        style={[
          styles.row,
          isTablet ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : null,
        ]}
      >
        {onBack ? (
          <Pressable
            onPress={onBack}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={backLabel ?? 'Go back'}
            style={({ pressed }) => [
              styles.back,
              {
                borderRadius: theme.radii.sm,
                backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
              },
            ]}
          >
            <Text role="title" tone="secondary" accessible={false}>
              ‹
            </Text>
          </Pressable>
        ) : null}

        <View style={styles.titles}>
          {eyebrow ? (
            <Text role="label" tone="tertiary" style={{ marginBottom: theme.spacing.xxs }}>
              {eyebrow}
            </Text>
          ) : null}
          <Text role="title" numberOfLines={1} accessibilityRole="header">
            {title}
          </Text>
          {subtitle ? (
            <Text role="caption" tone="secondary" numberOfLines={1}>
              {subtitle}
            </Text>
          ) : null}
        </View>

        {right ? <View style={styles.right}>{right}</View> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  back: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: -6,
  },
  titles: { flex: 1, minWidth: 0 },
  right: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
