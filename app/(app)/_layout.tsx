import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Tabs } from 'expo-router';
import type { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Text } from '@/components/primitives/Text';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';

const TAB_GLYPHS: Record<string, string> = {
  dashboard: '▣',
  cases: '≡',
  settings: '⚙',
};

const TAB_LABELS: Record<string, string> = {
  dashboard: 'Operations',
  cases: 'Cases',
  settings: 'Settings',
};

/**
 * The main tab bar.
 *
 * Written by hand rather than styled from the default so the glyph, label, and
 * active indicator can follow the same restrained language as the rest of the
 * application — a top rule marking the active tab, no pill, no colour fill.
 */
function TabBar({ state, navigation }: BottomTabBarProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { contentMaxWidth, isTablet } = useResponsive();

  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'center',
        backgroundColor: theme.color.surface,
        borderTopWidth: theme.borderWidth.thin,
        borderTopColor: theme.color.border,
        paddingBottom: insets.bottom,
      }}
    >
      <View
        style={[
          styles.inner,
          isTablet ? { maxWidth: contentMaxWidth, width: '100%' } : { flex: 1 },
        ]}
      >
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const label = TAB_LABELS[route.name] ?? route.name;

          return (
            <Pressable
              key={route.key}
              onPress={() => {
                const event = navigation.emit({
                  type: 'tabPress',
                  target: route.key,
                  canPreventDefault: true,
                });
                if (!focused && !event.defaultPrevented) {
                  navigation.navigate(route.name);
                }
              }}
              accessibilityRole="tab"
              accessibilityState={{ selected: focused }}
              accessibilityLabel={label}
              style={({ pressed }) => [
                styles.tab,
                {
                  minHeight: theme.controlHeight.large,
                  paddingTop: theme.spacing.sm,
                  paddingBottom: theme.spacing.sm,
                  borderTopWidth: theme.borderWidth.thick,
                  borderTopColor: focused ? theme.color.accent : 'transparent',
                  marginTop: -theme.borderWidth.thick,
                  opacity: pressed ? 0.7 : 1,
                },
              ]}
            >
              <Text
                role="body"
                style={{ color: focused ? theme.color.accent : theme.color.textTertiary }}
                accessible={false}
              >
                {TAB_GLYPHS[route.name] ?? '·'}
              </Text>
              <Text
                role="caption"
                weight={focused ? 'semibold' : 'regular'}
                style={{
                  color: focused ? theme.color.textPrimary : theme.color.textTertiary,
                  fontSize: 11,
                }}
                accessible={false}
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export default function AppTabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <TabBar {...props} />}
      screenOptions={{ headerShown: false, animation: 'none' }}
    >
      <Tabs.Screen name="dashboard" options={{ title: 'Operations' }} />
      <Tabs.Screen name="cases" options={{ title: 'Cases' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  inner: { flexDirection: 'row' },
  tab: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 2 },
});
