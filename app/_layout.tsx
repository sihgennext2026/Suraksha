import React, { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import * as SystemUI from 'expo-system-ui';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { getDatabase, syncQueueRepository } from '@/db';
import { useAuthStore } from '@/stores/authStore';
import { useConnectivityStore } from '@/stores/connectivityStore';
import { useScreeningStore } from '@/stores/screeningStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { ThemeProvider, buildTheme } from '@/theme';
import { createLogger } from '@/utils/logger';

const log = createLogger('boot');

void SplashScreen.preventAutoHideAsync();

/**
 * Query client.
 *
 * Retries are disabled and data never goes stale on its own: every query in this
 * application reads the local database, so a retry would repeat a query that
 * cannot transiently fail, and a background refetch would fight the explicit
 * invalidation the workflow already performs.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: Infinity,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
  },
});

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const themePreference = useSettingsStore((state) => state.theme);
  const startConnectivity = useConnectivityStore((state) => state.start);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        // Ordering matters: the database must be open and migrated before the
        // auth service can write enrolment records or the screening store can
        // recover an interrupted case.
        await getDatabase();
        await useSettingsStore.getState().hydrate();
        await useAuthStore.getState().bootstrap();
        await useScreeningStore.getState().restore();
        // Any entry left mid-flight by a crash goes back into the queue.
        await syncQueueRepository.recoverStranded();
      } catch (error) {
        // A failed boot must still reach the sign-in screen: the officer can do
        // nothing about a storage fault from a frozen splash screen.
        log.error('Startup did not complete cleanly');
        void error;
      } finally {
        if (!cancelled) setReady(true);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => startConnectivity(), [startConnectivity]);

  useEffect(() => {
    if (!ready) return;
    const theme = buildTheme(themePreference === 'light' ? 'light' : 'dark');
    void SystemUI.setBackgroundColorAsync(theme.color.canvas);
    void SplashScreen.hideAsync();
  }, [ready, themePreference]);

  if (!ready) {
    return <View style={[styles.root, { backgroundColor: '#0B1017' }]} />;
  }

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider preference={themePreference}>
            <StatusBar style={themePreference === 'light' ? 'dark' : 'light'} />
            <Stack
              screenOptions={{
                // Every screen supplies its own header so that the eyebrow,
                // sync state, and step counter can sit where the workflow needs
                // them rather than where a stock header allows.
                headerShown: false,
                animation: 'slide_from_right',
                contentStyle: { backgroundColor: 'transparent' },
              }}
            >
              <Stack.Screen name="index" />
              <Stack.Screen name="(auth)" />
              <Stack.Screen name="(app)" />
              <Stack.Screen name="screening" />
              <Stack.Screen name="case/[id]" />
            </Stack>
          </ThemeProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
