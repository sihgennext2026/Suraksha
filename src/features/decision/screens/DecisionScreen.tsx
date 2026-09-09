import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { TextField } from '@/components/primitives/TextField';
import { RiskBadge } from '@/components/data/StatusBadge';
import { ConfirmDialog } from '@/components/overlay/Sheet';
import { InlineNotice } from '@/components/feedback/States';
import { DECISION_PRESENTATION } from '@/constants/labels';
import { ROUTES } from '@/constants/routes';
import { useRefreshCases } from '@/features/cases/useCases';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useAuthStore, selectUser, hasPermission } from '@/stores/authStore';
import { useConnectivityStore, selectIsOnline } from '@/stores/connectivityStore';
import { useScreeningStore } from '@/stores/screeningStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { useTheme } from '@/theme';
import { hasEvidence } from '@/contracts';
import type { OfficerDecisionType, Permission } from '@/types';

const MAX_REMARKS = 500;

interface DecisionOption {
  value: OfficerDecisionType;
  title: string;
  description: string;
  permission: Permission;
}

const OPTIONS: DecisionOption[] = [
  {
    value: 'CLEAR',
    title: 'Clear',
    description: 'The subject and document are accepted. The subject may proceed.',
    permission: 'DECISION_CLEAR',
  },
  {
    value: 'HOLD',
    title: 'Hold for review',
    description: 'The subject is held at the post pending a further check by a supervisor.',
    permission: 'DECISION_HOLD',
  },
  {
    value: 'ESCALATE',
    title: 'Escalate',
    description: 'The case is referred for investigation under the post escalation procedure.',
    permission: 'DECISION_ESCALATE',
  },
];

/**
 * The officer's decision.
 *
 * This is the point the whole application exists to serve, and it is built
 * around one principle: the system assesses, the officer decides. The
 * recommendation is shown, but it is never pre-selected — an officer must make
 * an affirmative choice, and choosing against the recommendation is a first-class
 * outcome that is recorded as such rather than treated as an error.
 *
 * The decision is confirmed before it is committed, and the confirmation states
 * plainly that it will be recorded against the officer's name.
 */
export function DecisionScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('CASE');

  const user = useAuthStore(selectUser);
  const online = useConnectivityStore(selectIsOnline);
  const autoSync = useSettingsStore((state) => state.autoSync);

  const recordDecision = useScreeningStore((state) => state.recordDecision);
  const save = useScreeningStore((state) => state.save);
  const saving = useScreeningStore((state) => state.saving);
  const saveError = useScreeningStore((state) => state.saveError);
  const refreshCases = useRefreshCases();

  const [selected, setSelected] = useState<OfficerDecisionType | null>(null);
  const [remarks, setRemarks] = useState('');
  const [confirming, setConfirming] = useState(false);

  const risk =
    activeCase?.result && hasEvidence(activeCase.result.risk)
      ? activeCase.result.risk.result
      : null;
  // Derived from the band purely so a divergence can be recorded and flagged to
  // the officer. It never pre-selects an option.
  const recommendation: OfficerDecisionType | null = risk
    ? ({ LOW: 'CLEAR', REVIEW: 'HOLD', HIGH: 'ESCALATE' } as const)[risk.risk_level]
    : null;
  const diverges = selected !== null && recommendation !== null && selected !== recommendation;

  const available = useMemo(
    () => OPTIONS.filter((option) => hasPermission(user, option.permission)),
    [user],
  );

  const commit = useCallback(async () => {
    if (!selected) return;
    setConfirming(false);
    await recordDecision(selected, remarks);
    const savedId = await save({ autoSync, online });
    refreshCases();
    if (savedId) {
      // Replace the whole screening stack rather than pushing on top of it, so
      // going back from the saved case cannot return the officer to the result
      // screen of a decision they have already recorded.
      router.replace(ROUTES.app.dashboard);
      router.push(ROUTES.caseDetail(savedId));
    }
  }, [selected, recordDecision, remarks, save, autoSync, online, refreshCases, router]);

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Officer decision"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
        right={risk ? <RiskBadge level={risk.risk_level} size="small" /> : undefined}
      />

      <Screen
        footer={
          <Button
            label="Record decision"
            onPress={() => setConfirming(true)}
            disabled={!selected || saving}
            loading={saving}
            fullWidth
            haptic
            testID="decision-submit"
          />
        }
      >
        <Panel style={{ marginTop: theme.spacing.lg }} tone="sunken">
          <Text role="caption" tone="secondary">
            The screening produced decision support, not a decision. What you record here is the
            operational outcome, and it is stored against your name, your post and this timestamp.
          </Text>
        </Panel>

        {risk ? (
          <Panel style={{ marginTop: theme.spacing.md }}>
            <View style={styles.recommendationRow}>
              <View style={styles.recommendationText}>
                <Text role="label" tone="tertiary">
                  System recommendation
                </Text>
                <Text role="subtitle" style={{ marginTop: theme.spacing.xxs }}>
                  {recommendation ? DECISION_PRESENTATION[recommendation].label : '—'}
                </Text>
              </View>
              <Text role="mono" tone="tertiary">
                {risk.risk_level} · {risk.risk_score.toFixed(2)}
              </Text>
            </View>
          </Panel>
        ) : (
          <InlineNotice
            tone="caution"
            title="No risk assessment was produced"
            message="Screening did not complete for this case. Record your decision on the evidence that was gathered, and note the reason in your remarks."
          />
        )}

        <Section title="Your decision">
          <Panel padded={false}>
            {available.map((option, index) => {
              const isSelected = selected === option.value;
              const presentation = DECISION_PRESENTATION[option.value];
              const tone = {
                CLEAR: theme.color.positive,
                HOLD: theme.color.caution,
                ESCALATE: theme.color.critical,
              }[option.value];

              return (
                <Pressable
                  key={option.value}
                  onPress={() => setSelected(option.value)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: isSelected }}
                  accessibilityLabel={`${option.title}. ${option.description}`}
                  testID={`decision-${option.value}`}
                  style={({ pressed }) => [
                    styles.option,
                    {
                      padding: theme.spacing.lg,
                      minHeight: theme.controlHeight.minTouchTarget,
                      borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                      borderTopColor: theme.color.border,
                      backgroundColor: isSelected
                        ? theme.color.surfaceSunken
                        : pressed
                          ? theme.color.surfaceSunken
                          : 'transparent',
                    },
                  ]}
                >
                  <View
                    style={[
                      styles.radio,
                      {
                        borderRadius: theme.radii.pill,
                        borderWidth: isSelected ? 6 : theme.borderWidth.medium,
                        borderColor: isSelected ? tone : theme.color.borderStrong,
                      },
                    ]}
                  />
                  <View style={styles.optionBody}>
                    <View style={styles.optionHeader}>
                      <Text
                        role="body"
                        weight={isSelected ? 'semibold' : 'medium'}
                        accessible={false}
                      >
                        {option.title}
                      </Text>
                      <Text role="monoSmall" style={{ color: tone }} accessible={false}>
                        {presentation.glyph}
                      </Text>
                    </View>
                    <Text
                      role="caption"
                      tone="secondary"
                      style={{ marginTop: 2 }}
                      accessible={false}
                    >
                      {option.description}
                    </Text>
                  </View>
                </Pressable>
              );
            })}
          </Panel>

          {available.length < OPTIONS.length ? (
            <Text role="caption" tone="tertiary" style={{ marginTop: theme.spacing.sm }}>
              Some outcomes are not available at your permission level and are not shown.
            </Text>
          ) : null}
        </Section>

        {diverges ? (
          <InlineNotice
            tone="info"
            title="This differs from the system recommendation"
            message="That is expected and permitted — you have information the system does not. The divergence is recorded with the case so it can be reviewed later."
          />
        ) : null}

        <Section
          title="Remarks"
          description="Optional, but strongly advised when your decision differs from the recommendation."
        >
          <TextField
            label="Officer remarks"
            value={remarks}
            onChangeText={(text) => setRemarks(text.slice(0, MAX_REMARKS))}
            placeholder="What you observed, and why you decided as you did"
            multiline
            numberOfLines={4}
            maxLength={MAX_REMARKS}
            hint={`${remarks.length} of ${MAX_REMARKS} characters`}
            inputStyle={styles.remarks}
            testID="decision-remarks"
          />
        </Section>

        {saveError ? (
          <InlineNotice tone="critical" title="Could not save this case" message={saveError} />
        ) : null}

        {!online ? (
          <InlineNotice
            tone="info"
            title="This device is offline"
            message="The case will be saved here and uploaded automatically when a connection is available. Nothing is lost in the meantime."
          />
        ) : null}
      </Screen>

      <ConfirmDialog
        visible={confirming}
        title={selected ? `Record "${DECISION_PRESENTATION[selected].label}"?` : 'Record decision?'}
        message={
          selected
            ? `This will be recorded against ${user?.rank ?? ''} ${user?.name ?? 'you'} at ${activeCase.postName}, with the current time and the findings as they stand. It cannot be changed from this device.`
            : ''
        }
        confirmLabel="Record"
        destructive={selected === 'ESCALATE'}
        onConfirm={commit}
        onCancel={() => setConfirming(false)}
        testID="decision-confirm"
      />
    </>
  );
}

const styles = StyleSheet.create({
  recommendationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  recommendationText: { flex: 1, minWidth: 0 },
  option: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  radio: { width: 18, height: 18, marginTop: 2 },
  optionBody: { flex: 1, minWidth: 0 },
  optionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  remarks: { minHeight: 96, textAlignVertical: 'top' },
});
