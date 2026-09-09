import React from 'react';
import { Stack } from 'expo-router';

/**
 * The screening flow.
 *
 * Kept outside the tab navigator so an in-progress screening cannot be lost by
 * a stray tab tap: the officer is in the workflow until they finish it, discard
 * it, or deliberately navigate back to the dashboard.
 */
export default function ScreeningLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="document-capture" options={{ animation: 'fade' }} />
      <Stack.Screen name="person-capture" options={{ animation: 'fade' }} />
      <Stack.Screen name="progress" options={{ gestureEnabled: false }} />
      <Stack.Screen name="result" options={{ gestureEnabled: false }} />
    </Stack>
  );
}
