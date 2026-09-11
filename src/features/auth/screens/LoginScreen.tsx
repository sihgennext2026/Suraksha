import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View, type TextInput } from 'react-native';
import { useRouter } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { TextField } from '@/components/primitives/TextField';
import { BrandMark } from '@/components/brand/BrandMark';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { InlineNotice } from '@/components/feedback/States';
import { ROUTES } from '@/constants/routes';
import { ROLE_LABEL } from '@/constants/labels';
import { DEMO_CREDENTIALS } from '@/services/api/authService';
import { useAuthStore } from '@/stores/authStore';
import { useConnectivityStore, selectIsOnline } from '@/stores/connectivityStore';
import { useTheme } from '@/theme';

import { loginSchema, type LoginFormValues } from '../schemas';

/**
 * Sign-in.
 *
 * The screen states plainly that credentials are being checked against this
 * device rather than the central service. An officer at a post with no signal
 * needs to know that sign-in working does not imply the network is up — and
 * that nothing they do afterwards depends on it.
 */
export function LoginScreen() {
  const router = useRouter();
  const theme = useTheme();
  const pinRef = useRef<TextInput>(null);

  const signIn = useAuthStore((state) => state.signIn);
  const busy = useAuthStore((state) => state.busy);
  const authError = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const deviceId = useAuthStore((state) => state.deviceId);
  const online = useConnectivityStore(selectIsOnline);

  const [showHint, setShowHint] = useState(false);

  const { control, handleSubmit, setValue, formState } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { officerId: '', pin: '' },
    mode: 'onTouched',
  });

  useEffect(() => clearError, [clearError]);

  const onSubmit = useCallback(
    async (values: LoginFormValues) => {
      const success = await signIn({ officerId: values.officerId, pin: values.pin });
      if (success) router.replace(ROUTES.app.dashboard);
    },
    [signIn, router],
  );

  return (
    <Screen tone="canvas" contentStyle={{ paddingTop: theme.spacing.giant }}>
      <View style={styles.brand}>
        <BrandMark size={104} />
        <Text role="headline" style={{ marginTop: theme.spacing.lg }} accessibilityRole="header">
          SSB Suraksha
        </Text>
        <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
          Identity and document screening
        </Text>
      </View>

      <Panel style={{ marginTop: theme.spacing.xxxl }}>
        <Text role="subtitle">Officer sign-in</Text>
        <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xxs }}>
          Credentials are verified against this device, so screening remains available with no
          network.
        </Text>

        <Controller
          control={control}
          name="officerId"
          render={({ field, fieldState }) => (
            <TextField
              label="Officer ID"
              value={field.value}
              onChangeText={(text) => field.onChange(text.toUpperCase())}
              onBlur={field.onBlur}
              error={fieldState.error?.message}
              placeholder="SSB0000"
              autoCapitalize="characters"
              autoCorrect={false}
              autoComplete="username"
              maxLength={7}
              mono
              required
              returnKeyType="next"
              onSubmitEditing={() => pinRef.current?.focus()}
              containerStyle={{ marginTop: theme.spacing.xl }}
              testID="login-officer-id"
            />
          )}
        />

        <Controller
          control={control}
          name="pin"
          render={({ field, fieldState }) => (
            <TextField
              ref={pinRef}
              label="PIN"
              value={field.value}
              onChangeText={field.onChange}
              onBlur={field.onBlur}
              error={fieldState.error?.message}
              placeholder="••••"
              keyboardType="number-pad"
              maxLength={8}
              secure
              mono
              required
              returnKeyType="go"
              onSubmitEditing={handleSubmit(onSubmit)}
              containerStyle={{ marginTop: theme.spacing.lg }}
              testID="login-pin"
            />
          )}
        />

        {authError ? (
          <InlineNotice tone="critical" title="Sign-in failed" message={authError} />
        ) : null}

        <Button
          label="Sign in"
          onPress={handleSubmit(onSubmit)}
          loading={busy}
          disabled={busy || formState.isSubmitting}
          fullWidth
          style={{ marginTop: theme.spacing.xl }}
          testID="login-submit"
        />
      </Panel>

      <Section title="Device">
        <Panel padded={false}>
          <StatusLine label="Device" value={deviceId ?? 'Not enrolled'} mono />
          <StatusLine
            label="Authentication"
            value="On-device enrolment record"
            tone={theme.color.positive}
          />
          <StatusLine
            label="Network"
            value={online ? 'Online' : 'Offline'}
            tone={online ? theme.color.positive : theme.color.caution}
            last
          />
        </Panel>

        <Pressable
          onPress={() => router.push(ROUTES.auth.deviceSetup)}
          accessibilityRole="button"
          accessibilityLabel="Open device setup"
          style={({ pressed }) => [styles.link, { opacity: pressed ? 0.7 : 1 }]}
        >
          <Text role="caption" tone="accent" weight="semibold">
            Device setup and diagnostics ›
          </Text>
        </Pressable>
      </Section>

      <Section
        title="Demonstration accounts"
        description="This build ships with three enrolled officers so every permission level can be exercised."
        action={
          <Pressable
            onPress={() => setShowHint((current) => !current)}
            accessibilityRole="button"
            accessibilityLabel={
              showHint ? 'Hide demonstration accounts' : 'Show demonstration accounts'
            }
            hitSlop={8}
          >
            <Text role="caption" tone="accent" weight="semibold">
              {showHint ? 'Hide' : 'Show'}
            </Text>
          </Pressable>
        }
      >
        {showHint ? (
          <Panel padded={false}>
            {DEMO_CREDENTIALS.map((entry, index) => (
              <Pressable
                key={entry.officerId}
                onPress={() => {
                  setValue('officerId', entry.officerId, { shouldValidate: true });
                  setValue('pin', entry.pin, { shouldValidate: true });
                  clearError();
                }}
                accessibilityRole="button"
                accessibilityLabel={`Fill sign-in with ${entry.name}, ${ROLE_LABEL[entry.role]}`}
                style={({ pressed }) => [
                  styles.credentialRow,
                  {
                    padding: theme.spacing.lg,
                    borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                    borderTopColor: theme.color.border,
                    backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
                  },
                ]}
              >
                <View style={styles.credentialText}>
                  <Text role="body" weight="medium">
                    {entry.name}
                  </Text>
                  <Text role="caption" tone="tertiary">
                    {ROLE_LABEL[entry.role]}
                  </Text>
                </View>
                <Text role="monoSmall" tone="secondary">
                  {entry.officerId} · {entry.pin}
                </Text>
              </Pressable>
            ))}
          </Panel>
        ) : null}
      </Section>
    </Screen>
  );
}

function StatusLine({
  label,
  value,
  mono = false,
  tone,
  last = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: string;
  last?: boolean;
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.statusLine,
        {
          paddingVertical: theme.spacing.md,
          paddingHorizontal: theme.spacing.lg,
          borderBottomWidth: last ? 0 : theme.borderWidth.thin,
          borderBottomColor: theme.color.border,
        },
      ]}
    >
      <Text role="caption" tone="secondary">
        {label}
      </Text>
      <Text
        role={mono ? 'monoSmall' : 'caption'}
        weight="medium"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  brand: { alignItems: 'center' },
  statusLine: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  link: { marginTop: 12, alignSelf: 'flex-start' },
  credentialRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  credentialText: { flex: 1, minWidth: 0 },
});
