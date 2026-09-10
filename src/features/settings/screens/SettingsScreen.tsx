import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, View } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { TextField } from '@/components/primitives/TextField';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { SyncBadge } from '@/components/data/StatusBadge';
import { BottomSheet, ConfirmDialog } from '@/components/overlay/Sheet';
import { EmptyState, InlineNotice } from '@/components/feedback/States';
import { ROLE_LABEL } from '@/constants/labels';

import { ROUTES } from '@/constants/routes';
import { syncQueueRepository } from '@/db';
import { SystemStatusPanel } from '@/features/dashboard/components/SystemStatusPanel';
import { useSystemStatus } from '@/features/dashboard/useSystemStatus';
import { useRefreshCases } from '@/features/cases/useCases';
import { syncEngine } from '@/services/sync/syncEngine';
import { useAuthStore, selectUser } from '@/stores/authStore';
import {
  useConnectivityStore,
  selectIsOnline,
  connectionTypeLabel,
} from '@/stores/connectivityStore';
import { selectScreeningServiceUrl, useSettingsStore } from '@/stores/settingsStore';
import { useTheme } from '@/theme';
import type { ThemePreference } from '@/theme';
import { SCREENING_FIXTURES } from '@/services/mock/fixtures';
import { getIntegrationStatus, isUsingRealScreening } from '@/services/ai/registry';
import { normaliseServiceUrl } from '@/config/screeningService';
import { formatDateTime, formatRelative } from '@/utils/date';

/**
 * Settings, synchronisation, and diagnostics.
 *
 * The synchronisation section is the substantive part: it is where an officer
 * confirms that their work has left the device, and where they can act when it
 * has not. The diagnostics at the bottom exist so the failure paths — a stage
 * that fails mid-pipeline, a device that loses connectivity — can be
 * demonstrated on real hardware rather than only asserted in tests.
 */
export function SettingsScreen() {
  const router = useRouter();
  const theme = useTheme();

  const user = useAuthStore(selectUser);
  const signOut = useAuthStore((state) => state.signOut);
  const online = useConnectivityStore(selectIsOnline);
  const connectionType = useConnectivityStore((state) => state.connectionType);

  const serviceUrl = useSettingsStore(selectScreeningServiceUrl);
  const setScreeningServiceUrl = useSettingsStore((state) => state.setScreeningServiceUrl);
  // Held as a draft so a half-typed address is not saved on every keystroke and
  // does not blank the working one mid-edit.
  const [serviceUrlDraft, setServiceUrlDraft] = useState(serviceUrl ?? '');
  const commitServiceUrl = useCallback(() => {
    setScreeningServiceUrl(normaliseServiceUrl(serviceUrlDraft));
  }, [serviceUrlDraft, setScreeningServiceUrl]);
  const integrationStatus = useMemo(() => getIntegrationStatus(serviceUrl), [serviceUrl]);

  const themePreference = useSettingsStore((state) => state.theme);
  const setTheme = useSettingsStore((state) => state.setTheme);
  const autoSync = useSettingsStore((state) => state.autoSync);
  const setAutoSync = useSettingsStore((state) => state.setAutoSync);
  const haptics = useSettingsStore((state) => state.hapticFeedback);
  const setHaptics = useSettingsStore((state) => state.setHapticFeedback);
  const forcedScenario = useSettingsStore((state) => state.forcedScenario);
  const setForcedScenario = useSettingsStore((state) => state.setForcedScenario);

  const status = useSystemStatus();
  const refreshCases = useRefreshCases();

  const [syncing, setSyncing] = useState(false);
  const [confirmSignOut, setConfirmSignOut] = useState(false);
  const [failurePickerOpen, setFailurePickerOpen] = useState(false);

  const queue = useQuery({
    queryKey: ['sync-queue'],
    queryFn: () => syncQueueRepository.listAll(),
    staleTime: 5_000,
  });

  const runSync = useCallback(async () => {
    if (!user) return;
    setSyncing(true);
    try {
      await syncEngine.run({ online, actorId: user.officerId, actorName: user.name });
      await queue.refetch();
      status.refetch();
      refreshCases();
    } finally {
      setSyncing(false);
    }
  }, [user, online, queue, status, refreshCases]);

  const retryFailed = useCallback(async () => {
    await syncEngine.retryNow();
    await runSync();
  }, [runSync]);

  const entries = queue.data ?? [];
  const outstanding = entries.filter((entry) => entry.state !== 'COMPLETED');

  return (
    <>
      <AppHeader title="Settings" subtitle={user ? `${user.rank} ${user.name}` : undefined} />

      <Screen
        onRefresh={() => {
          void queue.refetch();
          status.refetch();
        }}
        refreshing={queue.isFetching}
      >
        {user ? (
          <Panel style={{ marginTop: theme.spacing.lg }} padded={false}>
            <KeyValueRow label="Officer" value={`${user.rank} ${user.name}`} />
            <KeyValueRow label="Officer ID" value={user.officerId} mono />
            <KeyValueRow label="Permission level" value={ROLE_LABEL[user.role]} />
            <KeyValueRow label="Unit" value={user.unit} />
            <KeyValueRow label="Post" value={user.postName} />
            <KeyValueRow label="Device" value={user.deviceId} mono />
          </Panel>
        ) : null}

        <Section
          title="Synchronisation"
          description="Cases are stored on this device first and uploaded when a connection allows."
        >
          <Panel padded={false}>
            <KeyValueRow
              label="Network"
              value={online ? connectionTypeLabel(connectionType) : 'Offline'}
              hint={online ? 'Upload available' : 'Screening is unaffected'}
            />
            <KeyValueRow
              label="Queued"
              value={`${status.pendingSync} ${status.pendingSync === 1 ? 'case' : 'cases'}`}
            />
            {status.failedSync > 0 ? (
              <KeyValueRow
                label="Failed"
                value={`${status.failedSync} ${status.failedSync === 1 ? 'case' : 'cases'}`}
              />
            ) : null}
            <ToggleRow
              label="Automatic synchronisation"
              hint="Upload each case as soon as it is saved, when a connection is available."
              value={autoSync}
              onChange={setAutoSync}
            />
          </Panel>

          <View style={[styles.syncActions, { marginTop: theme.spacing.md }]}>
            <Button
              label={online ? 'Sync now' : 'Offline'}
              onPress={runSync}
              loading={syncing}
              disabled={!online || status.pendingSync === 0}
              variant="secondary"
              size="medium"
            />
            {status.failedSync > 0 ? (
              <Button
                label="Retry failed"
                onPress={retryFailed}
                disabled={!online}
                variant="secondary"
                size="medium"
              />
            ) : null}
          </View>

          {!online && status.pendingSync > 0 ? (
            <InlineNotice
              tone="info"
              title={`${status.pendingSync} ${status.pendingSync === 1 ? 'case is' : 'cases are'} waiting`}
              message="They will upload automatically once this device has a connection. Nothing needs to be done."
            />
          ) : null}
        </Section>

        <Section title="Sync queue">
          {outstanding.length === 0 ? (
            <Panel>
              <EmptyState
                glyph="✓"
                title="Nothing queued"
                message="Every case on this device has been uploaded."
              />
            </Panel>
          ) : (
            <Panel padded={false}>
              {outstanding.map((entry, index) => (
                <Pressable
                  key={entry.id}
                  onPress={() => router.push(ROUTES.caseDetail(entry.caseId))}
                  accessibilityRole="button"
                  accessibilityLabel={`Case ${entry.caseId}, ${entry.state.toLowerCase()}, ${entry.attempts} attempts`}
                  style={({ pressed }) => [
                    styles.queueRow,
                    {
                      padding: theme.spacing.lg,
                      borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                      borderTopColor: theme.color.border,
                      backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
                    },
                  ]}
                >
                  <View style={styles.queueText}>
                    <Text role="mono" weight="semibold" accessible={false}>
                      {entry.caseId}
                    </Text>
                    <Text role="caption" tone="tertiary" accessible={false}>
                      Queued {formatRelative(entry.enqueuedAt)}
                      {entry.attempts > 0
                        ? ` · ${entry.attempts} ${entry.attempts === 1 ? 'attempt' : 'attempts'}`
                        : ''}
                    </Text>
                    {entry.lastError ? (
                      <Text
                        role="caption"
                        tone="critical"
                        style={{ marginTop: 2 }}
                        accessible={false}
                      >
                        {entry.lastError}
                      </Text>
                    ) : null}
                  </View>
                  <SyncBadge
                    state={
                      entry.state === 'FAILED'
                        ? 'FAILED'
                        : entry.state === 'IN_FLIGHT'
                          ? 'SYNCING'
                          : 'PENDING'
                    }
                    size="small"
                  />
                </Pressable>
              ))}
            </Panel>
          )}
        </Section>

        <Section title="Appearance">
          <Panel padded={false}>
            <View style={{ padding: theme.spacing.lg }}>
              <Text role="body">Theme</Text>
              <Text role="caption" tone="tertiary" style={{ marginTop: 2 }}>
                Dark is the default for field use at night. Light is more legible in direct
                sunlight.
              </Text>
              <View style={[styles.themeRow, { marginTop: theme.spacing.md }]}>
                {(['dark', 'light', 'system'] as ThemePreference[]).map((option) => {
                  const active = themePreference === option;
                  return (
                    <Pressable
                      key={option}
                      onPress={() => setTheme(option)}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: active }}
                      accessibilityLabel={`${option} theme`}
                      style={[
                        styles.themeOption,
                        {
                          borderRadius: theme.radii.sm,
                          borderWidth: theme.borderWidth.thin,
                          borderColor: active ? theme.color.accent : theme.color.border,
                          backgroundColor: active ? theme.color.accentSubtle : 'transparent',
                          paddingVertical: theme.spacing.sm,
                        },
                      ]}
                    >
                      <Text
                        role="caption"
                        weight={active ? 'semibold' : 'regular'}
                        tone={active ? 'accent' : 'secondary'}
                        accessible={false}
                      >
                        {option.charAt(0).toUpperCase() + option.slice(1)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
            <ToggleRow
              label="Haptic feedback"
              hint="A short pulse when a capture is taken or a decision is recorded."
              value={haptics}
              onChange={setHaptics}
            />
          </Panel>
        </Section>

        <Section
          title="Integration status"
          description="What each check is backed by today. Read this before quoting a finding."
        >
          <Panel padded={false}>
            {integrationStatus.map((entry, index) => (
              <View
                key={entry.module}
                accessible
                accessibilityRole="text"
                accessibilityLabel={`${entry.module}. ${entry.state.replace(/_/g, ' ').toLowerCase()}. ${entry.note}`}
                style={{
                  padding: theme.spacing.lg,
                  borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                  borderTopColor: theme.color.border,
                }}
              >
                <View style={styles.queueRow}>
                  <Text role="body" weight="medium" style={styles.queueText} accessible={false}>
                    {entry.module}
                  </Text>
                  <Text
                    role="monoSmall"
                    weight="bold"
                    style={{
                      color:
                        entry.state === 'ACTIVE'
                          ? theme.color.positive
                          : entry.state === 'MOCK'
                            ? theme.color.caution
                            : theme.color.textTertiary,
                    }}
                    accessible={false}
                  >
                    {entry.state}
                  </Text>
                </View>
                <Text role="caption" tone="tertiary" style={{ marginTop: 2 }} accessible={false}>
                  {entry.implementation}
                </Text>
                <Text
                  role="caption"
                  tone="secondary"
                  style={{ marginTop: theme.spacing.xs }}
                  accessible={false}
                >
                  {entry.note}
                </Text>
              </View>
            ))}
          </Panel>
        </Section>

        <Section title="Device status">
          <SystemStatusPanel subsystems={status.subsystems} />
        </Section>

        <Section
          title="Screening service"
          description="Where the models run. Extraction, rule validation and face verification need this address; everything else works without it."
        >
          <Panel>
            <TextField
              label="Service address"
              value={serviceUrlDraft}
              onChangeText={setServiceUrlDraft}
              onBlur={commitServiceUrl}
              placeholder="http://10.0.0.5:8000"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              mono
              error={serviceUrlDraft.trim() && !normaliseServiceUrl(serviceUrlDraft) ? 'Enter a full address, for example http://10.0.0.5:8000' : undefined}
              hint="Leave empty to fall back to the address this build shipped with."
            />
          </Panel>

          {isUsingRealScreening(serviceUrl) ? null : (
            <InlineNotice
              tone="caution"
              title="No screening service is configured"
              message="Screenings replay a generated document. Nothing shown comes from the capture, and the integration table below says so for each module."
            />
          )}
        </Section>

        <Section
          title="Diagnostics"
          description="For demonstrating and testing the failure paths on real hardware."
        >
          <Panel padded={false}>
            <KeyValueRow
              label="Force a screening scenario"
              value={forcedScenario ? scenarioLabel(forcedScenario) : 'Off'}
              hint="Replays a chosen outcome on the next screening, including tampering and failed modules."
              onPress={() => setFailurePickerOpen(true)}
              trailing={
                <Text role="body" tone="tertiary">
                  ›
                </Text>
              }
            />
          </Panel>

          {forcedScenario ? (
            <InlineNotice
              tone="caution"
              title="A screening scenario is being forced"
              message={`Every screening will replay "${scenarioLabel(forcedScenario)}" until this is switched off.`}
              actionLabel="Switch off"
              onAction={() => setForcedScenario(null)}
            />
          ) : null}
        </Section>

        <Section title="Session">
          <Panel padded={false}>
            <KeyValueRow
              label="Signed in"
              value={
                useAuthStore.getState().session
                  ? formatDateTime(useAuthStore.getState().session?.issuedAt)
                  : '—'
              }
            />
            <KeyValueRow
              label="Verified against"
              value="On-device enrolment record"
              hint="Sign-in does not require a network connection"
            />
          </Panel>

          <Button
            label="Sign out"
            onPress={() => setConfirmSignOut(true)}
            variant="secondary"
            fullWidth
            style={{ marginTop: theme.spacing.md }}
          />
        </Section>
      </Screen>

      <BottomSheet
        visible={failurePickerOpen}
        onDismiss={() => setFailurePickerOpen(false)}
        title="Force a screening scenario"
        description="Replays a known outcome so every state the officer can meet is reachable on real hardware."
      >
        <Panel padded={false} style={{ marginBottom: theme.spacing.xl }}>
          <Pressable
            onPress={() => {
              setForcedScenario(null);
              setFailurePickerOpen(false);
            }}
            accessibilityRole="radio"
            accessibilityState={{ selected: forcedScenario === null }}
            accessibilityLabel="Off, choose the scenario from the case reference"
            style={{ padding: theme.spacing.lg }}
          >
            <Text
              role="body"
              weight={forcedScenario === null ? 'semibold' : 'regular'}
              accessible={false}
            >
              Off
            </Text>
            <Text role="caption" tone="tertiary" accessible={false}>
              Each case replays the scenario derived from its own reference
            </Text>
          </Pressable>
          {SCREENING_FIXTURES.map((fixture) => (
            <Pressable
              key={fixture.id}
              onPress={() => {
                setForcedScenario(fixture.id);
                setFailurePickerOpen(false);
              }}
              accessibilityRole="radio"
              accessibilityState={{ selected: forcedScenario === fixture.id }}
              accessibilityLabel={scenarioLabel(fixture.id)}
              style={{
                padding: theme.spacing.lg,
                borderTopWidth: theme.borderWidth.thin,
                borderTopColor: theme.color.border,
              }}
            >
              <Text
                role="body"
                weight={forcedScenario === fixture.id ? 'semibold' : 'regular'}
                accessible={false}
              >
                {scenarioLabel(fixture.id)}
              </Text>
              <Text role="monoSmall" tone="tertiary" accessible={false}>
                {fixture.result.document_type} · risk{' '}
                {fixture.result.risk.result?.risk_level ?? 'n/a'}
              </Text>
            </Pressable>
          ))}
        </Panel>
      </BottomSheet>

      <ConfirmDialog
        visible={confirmSignOut}
        title="Sign out?"
        message="Cases already saved on this device are kept and will still upload. Any screening in progress must be finished or discarded first."
        confirmLabel="Sign out"
        onConfirm={async () => {
          setConfirmSignOut(false);
          await signOut();
          router.replace(ROUTES.auth.login);
        }}
        onCancel={() => setConfirmSignOut(false)}
      />
    </>
  );
}

/** `tampered-photo-replacement` reads as `Tampered photo replacement`. */
function scenarioLabel(id: string): string {
  const words = id.replace(/-/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function ToggleRow({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (next: boolean) => void;
}) {
  const theme = useTheme();
  return (
    <View
      style={[
        styles.toggleRow,
        {
          padding: theme.spacing.lg,
          borderTopWidth: theme.borderWidth.thin,
          borderTopColor: theme.color.border,
          minHeight: theme.controlHeight.minTouchTarget,
        },
      ]}
    >
      <View style={styles.toggleText}>
        <Text role="body">{label}</Text>
        <Text role="caption" tone="tertiary" style={{ marginTop: 2 }}>
          {hint}
        </Text>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={label}
        trackColor={{ false: theme.color.neutralBorder, true: theme.color.accent }}
        thumbColor={theme.color.surface}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  syncActions: { flexDirection: 'row', gap: 8 },
  queueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  queueText: { flex: 1, minWidth: 0 },
  themeRow: { flexDirection: 'row', gap: 8 },
  themeOption: { flex: 1, alignItems: 'center' },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  toggleText: { flex: 1, minWidth: 0 },
});
