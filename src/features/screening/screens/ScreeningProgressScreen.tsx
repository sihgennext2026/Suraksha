import React, { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { ScreeningStep } from '@/components/data/ScreeningStep';
import { InlineNotice } from '@/components/feedback/States';
import { ConfirmDialog } from '@/components/overlay/Sheet';
import { ROUTES } from '@/constants/routes';
import { useScreeningStore } from '@/stores/screeningStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { useTheme } from '@/theme';
import { formatDurationMs } from '@/utils/format';

import { useScreeningGuard } from '../useScreeningGuard';

/**
 * Step 5 — the screening pipeline.
 *
 * Eight named stages, each with its own state and its own one-line finding. An
 * officer watching this screen can tell which stage is running, what the ones
 * before it concluded, and — when something fails — exactly where it stopped.
 * A single indeterminate spinner would communicate none of that, and would make
 * a stalled run indistinguishable from a slow one.
 */
export function ScreeningProgressScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('PERSON');

  const running = useScreeningStore((state) => state.running);
  const error = useScreeningStore((state) => state.error);
  const runScreening = useScreeningStore((state) => state.runScreening);
  const cancelScreening = useScreeningStore((state) => state.cancelScreening);
  const scenario = useSettingsStore((state) => state.forcedScenario);

  const [confirmCancel, setConfirmCancel] = useState(false);

  const stages = activeCase?.stages ?? [];
  const complete = Boolean(activeCase?.result);

  // The run is started by the subject capture that navigated here, so this
  // screen is a pure view of a run already under way. `runAgain` is the only
  // path that starts one, and it is driven by an explicit officer action.
  const runAgain = useCallback(() => {
    void runScreening({ scenario: scenario ?? undefined });
  }, [runScreening, scenario]);

  useEffect(() => {
    if (complete && !running) {
      router.replace(ROUTES.screening.result);
    }
  }, [complete, running, router]);

  if (!activeCase) return null;

  const completedCount = stages.filter(
    (stage) => stage.status === 'COMPLETED' || stage.status === 'WARNING',
  ).length;
  const elapsed = stages.reduce((total, stage) => {
    if (!stage.startedAt || !stage.completedAt) return total;
    return total + (new Date(stage.completedAt).getTime() - new Date(stage.startedAt).getTime());
  }, 0);

  return (
    <>
      <AppHeader
        title="Screening"
        eyebrow="Step 5 of 5"
        subtitle={activeCase.id}
        onBack={running ? () => setConfirmCancel(true) : () => router.back()}
        backLabel={running ? 'Stop the screening' : 'Back to subject capture'}
      />

      <Screen
        footer={
          error ? (
            <View style={styles.footer}>
              <Button
                label="Back to capture"
                onPress={() => router.back()}
                variant="secondary"
                style={styles.footerSecondary}
              />
              <Button label="Run again" onPress={runAgain} style={styles.footerPrimary} />
            </View>
          ) : undefined
        }
      >
        <Panel style={{ marginTop: theme.spacing.lg }} level="low">
          <View style={styles.summaryRow}>
            <View style={styles.summaryText}>
              <Text role="label" tone="tertiary">
                {running ? 'Running' : error ? 'Stopped' : 'Complete'}
              </Text>
              <Text role="title" style={{ marginTop: theme.spacing.xxs }}>
                {completedCount} of {stages.length} stages
              </Text>
            </View>
            <Text role="monoSmall" tone="tertiary">
              {elapsed > 0 ? formatDurationMs(elapsed) : '—'}
            </Text>
          </View>

          <View
            style={[
              styles.track,
              { backgroundColor: theme.color.neutralSubtle, marginTop: theme.spacing.lg },
            ]}
          >
            <View
              style={{
                width: `${(completedCount / Math.max(1, stages.length)) * 100}%`,
                height: '100%',
                backgroundColor: error ? theme.color.critical : theme.color.accent,
              }}
            />
          </View>

          <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.md }}>
            Every stage runs on this device. No case data leaves it while the screening is in
            progress.
          </Text>
        </Panel>

        {error ? <InlineNotice tone="critical" title="Screening stopped" message={error} /> : null}

        <Section title="Pipeline">
          <Panel>
            {stages.map((stage, index) => (
              <View key={stage.id} style={index > 0 ? undefined : undefined}>
                <ScreeningStep stage={stage} connected={index < stages.length - 1} />
              </View>
            ))}
          </Panel>
        </Section>

        {error ? (
          <Section title="What you can do">
            <Panel tone="sunken">
              <Text role="caption" tone="secondary">
                You can run the screening again from the same captures, retake the document
                or subject photograph, or record a decision on your own examination. A check
                that did not run has produced no finding either way.
              </Text>
            </Panel>
          </Section>
        ) : null}
      </Screen>

      <ConfirmDialog
        visible={confirmCancel}
        title="Stop the screening?"
        message="The stages that have already completed are kept. You can run the screening again from the same captures."
        confirmLabel="Stop"
        destructive
        onConfirm={() => {
          setConfirmCancel(false);
          cancelScreening();
          router.back();
        }}
        onCancel={() => setConfirmCancel(false)}
      />
    </>
  );
}

const styles = StyleSheet.create({
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  summaryText: { flex: 1, minWidth: 0 },
  track: { height: 4, borderRadius: 2, overflow: 'hidden' },
  footer: { flexDirection: 'row', gap: 8 },
  footerSecondary: { flexShrink: 0 },
  footerPrimary: { flex: 1 },
});
