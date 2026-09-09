import React, { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { MetricCard } from '@/components/data/MetricCard';
import { SyncIndicator } from '@/components/data/SyncIndicator';
import { EmptyState, InlineNotice, LoadingState } from '@/components/feedback/States';
import { ConfirmDialog } from '@/components/overlay/Sheet';
import { ROUTES } from '@/constants/routes';
import { CaseRow } from '@/features/cases/components/CaseRow';
import { useCaseCounts, useCaseSummaries, useRefreshCases } from '@/features/cases/useCases';
import { useAuthStore, selectUser } from '@/stores/authStore';
import { useConnectivityStore, selectIsOnline } from '@/stores/connectivityStore';
import { useScreeningStore } from '@/stores/screeningStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { syncEngine } from '@/services/sync/syncEngine';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';

import { SystemStatusPanel } from '../components/SystemStatusPanel';
import { useSystemStatus } from '../useSystemStatus';

/**
 * The operations screen.
 *
 * Built around one question: can this officer start a screening right now, and
 * is anything outstanding from earlier? The primary action is the largest
 * element on the screen; everything else is a read-out that either confirms the
 * device is ready or names what is not.
 */
export function DashboardScreen() {
  const router = useRouter();
  const theme = useTheme();
  const { isTablet } = useResponsive();

  const user = useAuthStore(selectUser);
  const online = useConnectivityStore(selectIsOnline);
  const autoSync = useSettingsStore((state) => state.autoSync);

  const storedCase = useScreeningStore((state) => state.activeCase);
  const activePhase = useScreeningStore((state) => state.phase);
  const startCase = useScreeningStore((state) => state.start);
  const abandonCase = useScreeningStore((state) => state.abandon);
  const clearScreening = useScreeningStore((state) => state.clear);

  // A case that reached SAVED is finished. It is released here rather than at
  // the moment of saving, so the decision screen keeps a valid case underneath
  // it until it has navigated away.
  const activeCase = activePhase === 'SAVED' || activePhase === 'IDLE' ? null : storedCase;

  const status = useSystemStatus();
  const counts = useCaseCounts();
  const recent = useCaseSummaries({ limit: 5 });
  const refreshCases = useRefreshCases();

  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [starting, setStarting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      if (useScreeningStore.getState().phase === 'SAVED') clearScreening();
      refreshCases();
      status.refetch();
      // `status.refetch` is stable across renders from the query client, and
      // including the whole status object would refetch on every state change.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [refreshCases, clearScreening]),
  );

  const handleRefresh = useCallback(() => {
    refreshCases();
    status.refetch();
    void useConnectivityStore.getState().refresh();
  }, [refreshCases, status]);

  const beginScreening = useCallback(async () => {
    if (!user) return;
    setStarting(true);
    try {
      await startCase(user);
      router.push(ROUTES.screening.documentType);
    } finally {
      setStarting(false);
    }
  }, [user, startCase, router]);

  const resumeScreening = useCallback(() => {
    const route =
      activePhase === 'DOCUMENT_TYPE'
        ? ROUTES.screening.documentType
        : activePhase === 'DOCUMENT_CAPTURE'
          ? ROUTES.screening.documentCapture
          : activePhase === 'DOCUMENT_REVIEW'
            ? ROUTES.screening.documentReview
            : activePhase === 'PERSON_CAPTURE'
              ? ROUTES.screening.personCapture
              : activePhase === 'RESULT' || activePhase === 'DECISION'
                ? ROUTES.screening.result
                : ROUTES.screening.progress;
    router.push(route);
  }, [activePhase, router]);

  const runSync = useCallback(async () => {
    if (!user) return;
    await syncEngine.run({ online, actorId: user.officerId, actorName: user.name });
    handleRefresh();
  }, [user, online, handleRefresh]);

  const countData = counts.data;

  return (
    <>
      <AppHeader
        title={user ? `${user.rank} ${user.name}` : 'Operations'}
        subtitle={user ? `${user.unit} · ${user.postName}` : undefined}
        eyebrow="SSB Suraksha"
        right={
          <SyncIndicator
            online={online}
            pending={status.pendingSync}
            syncing={false}
            onPress={() => router.push(ROUTES.app.settings)}
          />
        }
      />

      <Screen onRefresh={handleRefresh} refreshing={status.isLoading || recent.isFetching}>
        {activeCase ? (
          <InlineNotice
            tone="caution"
            title={`Screening ${activeCase.id} is still open`}
            message="A screening was started and not completed. Resume it, or discard it and start again."
            actionLabel="Resume screening"
            onAction={resumeScreening}
          />
        ) : null}

        {activeCase ? (
          <Button
            label="Discard this screening"
            onPress={() => setConfirmDiscard(true)}
            variant="ghost"
            size="medium"
            style={{ marginTop: theme.spacing.sm, alignSelf: 'flex-start' }}
          />
        ) : (
          <Panel style={{ marginTop: theme.spacing.lg }} level="low">
            <Text role="label" tone="tertiary">
              Start
            </Text>
            <Text role="title" style={{ marginTop: theme.spacing.xs }}>
              New screening
            </Text>
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
              Select the document type, capture the document and the subject, then run the
              screening. Everything works without a network.
            </Text>
            <Button
              label="Begin screening"
              onPress={beginScreening}
              loading={starting}
              fullWidth
              haptic
              style={{ marginTop: theme.spacing.lg }}
              testID="dashboard-begin-screening"
            />
          </Panel>
        )}

        <Section title="Caseload">
          {counts.isLoading ? (
            <LoadingState label="Reading case counts" fill={false} />
          ) : (
            <View style={styles.metricGrid}>
              <View style={styles.metricRow}>
                <MetricCard
                  label="Active"
                  value={String(countData?.active ?? 0)}
                  caption="in progress"
                  tone={(countData?.active ?? 0) > 0 ? 'accent' : 'neutral'}
                  onPress={() => router.push(ROUTES.app.cases)}
                />
                <MetricCard
                  label="Awaiting decision"
                  value={String(countData?.awaitingDecision ?? 0)}
                  caption="screened, undecided"
                  tone={(countData?.awaitingDecision ?? 0) > 0 ? 'caution' : 'neutral'}
                  onPress={() => router.push(ROUTES.app.cases)}
                />
              </View>
              <View style={[styles.metricRow, { marginTop: theme.spacing.md }]}>
                <MetricCard
                  label="High risk"
                  value={String(countData?.highRisk ?? 0)}
                  caption="all time"
                  tone={(countData?.highRisk ?? 0) > 0 ? 'critical' : 'neutral'}
                  onPress={() => router.push(ROUTES.app.cases)}
                />
                <MetricCard
                  label="Pending sync"
                  value={String(status.pendingSync)}
                  caption={online ? 'uploading when ready' : 'held on device'}
                  tone={status.pendingSync > 0 ? 'caution' : 'positive'}
                  onPress={() => router.push(ROUTES.app.settings)}
                />
              </View>
              {isTablet ? (
                <View style={[styles.metricRow, { marginTop: theme.spacing.md }]}>
                  <MetricCard
                    label="Completed today"
                    value={String(countData?.completedToday ?? 0)}
                    caption="since midnight"
                  />
                  <MetricCard
                    label="Total cases"
                    value={String(countData?.total ?? 0)}
                    caption="held on this device"
                  />
                </View>
              ) : null}
            </View>
          )}
        </Section>

        {status.failedSync > 0 ? (
          <InlineNotice
            tone="critical"
            title={`${status.failedSync} ${status.failedSync === 1 ? 'case' : 'cases'} failed to upload`}
            message="The cases are safe on this device. Retry now, or leave them queued for the next automatic attempt."
            actionLabel="Retry now"
            onAction={async () => {
              await syncEngine.retryNow();
              await runSync();
            }}
          />
        ) : status.pendingSync > 0 && online && !autoSync ? (
          <InlineNotice
            tone="info"
            title={`${status.pendingSync} ${status.pendingSync === 1 ? 'case' : 'cases'} queued`}
            message="Automatic synchronisation is switched off for this device."
            actionLabel="Sync now"
            onAction={runSync}
          />
        ) : null}

        <Section title="System status" description="Checked on this device, not over the network.">
          <SystemStatusPanel subsystems={status.subsystems} />
        </Section>

        <Section
          title="Recent cases"
          action={
            <Button
              label="View all"
              onPress={() => router.push(ROUTES.app.cases)}
              variant="ghost"
              size="medium"
            />
          }
        >
          {recent.isLoading ? (
            <LoadingState label="Reading recent cases" fill={false} />
          ) : (recent.data ?? []).length === 0 ? (
            <Panel>
              <EmptyState
                title="No cases yet"
                message="Cases you screen on this device appear here, whether or not they have been uploaded."
              />
            </Panel>
          ) : (
            <Panel padded={false}>
              {(recent.data ?? []).map((summary, index) => (
                <CaseRow
                  key={summary.id}
                  summary={summary}
                  separated={index > 0}
                  onPress={(id) => router.push(ROUTES.caseDetail(id))}
                />
              ))}
            </Panel>
          )}
        </Section>
      </Screen>

      <ConfirmDialog
        visible={confirmDiscard}
        title="Discard this screening?"
        message={`Case ${activeCase?.id ?? ''} will be marked abandoned and its captures deleted. The audit record that it was started is kept.`}
        confirmLabel="Discard"
        destructive
        onConfirm={async () => {
          setConfirmDiscard(false);
          await abandonCase();
          handleRefresh();
        }}
        onCancel={() => setConfirmDiscard(false)}
      />
    </>
  );
}

const styles = StyleSheet.create({
  metricGrid: {},
  metricRow: { flexDirection: 'row', gap: 12 },
});
