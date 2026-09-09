import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { EvidenceTimeline } from '@/components/data/EvidenceTimeline';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { RiskMeter } from '@/components/data/RiskMeter';
import {
  CaseStatusBadge,
  DecisionBadge,
  RiskBadge,
  SyncBadge,
} from '@/components/data/StatusBadge';
import { EmptyState, ErrorState, InlineNotice, LoadingState } from '@/components/feedback/States';
import { documentTypeLabel } from '@/constants/documents';
import { SCREENING_STAGE_DESCRIPTORS } from '@/constants/screening';
import { hasEvidence } from '@/contracts';
import { AnomalyDetails } from '@/features/anomaly/components/AnomalyDetails';
import { FaceDetails } from '@/features/face/components/FaceDetails';
import { ForensicsDetails } from '@/features/forensics/components/ForensicsDetails';
import { OcrDetails } from '@/features/ocr/components/OcrDetails';
import { ValidationDetails } from '@/features/validation/components/ValidationDetails';
import { syncEngine } from '@/services/sync/syncEngine';
import { useAuthStore, selectUser } from '@/stores/authStore';
import { useConnectivityStore, selectIsOnline } from '@/stores/connectivityStore';
import { useTheme } from '@/theme';
import { formatDateTime } from '@/utils/date';

import { useCaseAudit, useCaseDetail, useRefreshCases } from '../useCases';

type Tab = 'SUMMARY' | 'DOCUMENT' | 'ANALYSIS' | 'AUDIT';

const TABS: { value: Tab; label: string }[] = [
  { value: 'SUMMARY', label: 'Summary' },
  { value: 'DOCUMENT', label: 'Document' },
  { value: 'ANALYSIS', label: 'Analysis' },
  { value: 'AUDIT', label: 'Audit' },
];

/**
 * A saved case.
 *
 * Reuses the same detail components the live screening uses, so a case reviewed
 * a month later shows exactly what the officer saw at the counter — including
 * the risk level and score as they stood when the decision was recorded, which
 * is stored on the decision itself rather than recomputed.
 */
export function CaseDetailScreen() {
  const router = useRouter();
  const theme = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();

  const user = useAuthStore(selectUser);
  const online = useConnectivityStore(selectIsOnline);
  const refreshCases = useRefreshCases();

  const detail = useCaseDetail(id);
  const audit = useCaseAudit(id);
  const [tab, setTab] = useState<Tab>('SUMMARY');
  const [syncing, setSyncing] = useState(false);

  const handleRetrySync = useCallback(async () => {
    if (!user) return;
    setSyncing(true);
    try {
      await syncEngine.retryNow();
      await syncEngine.run({ online, actorId: user.officerId, actorName: user.name });
      refreshCases();
    } finally {
      setSyncing(false);
    }
  }, [user, online, refreshCases]);

  if (detail.isLoading) {
    return (
      <>
        <AppHeader title="Case" onBack={() => router.back()} />
        <LoadingState label="Reading the case record" />
      </>
    );
  }

  if (detail.isError) {
    return (
      <>
        <AppHeader title="Case" onBack={() => router.back()} />
        <ErrorState
          title="This case could not be read"
          message="The local case store could not return this record. Restart the application, and report the fault if it repeats."
          actionLabel="Try again"
          onAction={() => void detail.refetch()}
        />
      </>
    );
  }

  const screeningCase = detail.data;
  if (!screeningCase) {
    return (
      <>
        <AppHeader title="Case" onBack={() => router.back()} />
        <EmptyState
          title="Case not found"
          message="This case is not held on this device. It may have been removed under the retention policy."
          actionLabel="Back to cases"
          onAction={() => router.back()}
        />
      </>
    );
  }

  const caseResult = screeningCase.result;
  const risk = caseResult && hasEvidence(caseResult.risk) ? caseResult.risk.result : null;
  const decision = screeningCase.decision;
  const documentUri = screeningCase.document?.image.uri;
  const personUri = screeningCase.person?.image.uri;

  return (
    <>
      <AppHeader
        title={screeningCase.id}
        subtitle={`${documentTypeLabel(screeningCase.documentType)} · ${formatDateTime(screeningCase.createdAt)}`}
        onBack={() => router.back()}
        backLabel="Back to cases"
        right={risk ? <RiskBadge level={risk.risk_level} size="small" /> : undefined}
      />

      <View style={[styles.tabBar, { backgroundColor: theme.color.surface }]}>
        <View
          style={[
            styles.tabRow,
            {
              paddingHorizontal: theme.spacing.lg,
              borderBottomWidth: theme.borderWidth.thin,
              borderBottomColor: theme.color.border,
            },
          ]}
        >
          {TABS.map((entry) => {
            const active = tab === entry.value;
            return (
              <Pressable
                key={entry.value}
                onPress={() => setTab(entry.value)}
                accessibilityRole="tab"
                accessibilityState={{ selected: active }}
                accessibilityLabel={entry.label}
                style={[
                  styles.tab,
                  {
                    paddingVertical: theme.spacing.md,
                    borderBottomWidth: theme.borderWidth.thick,
                    borderBottomColor: active ? theme.color.accent : 'transparent',
                    marginBottom: -theme.borderWidth.thin,
                  },
                ]}
              >
                <Text
                  role="caption"
                  weight={active ? 'semibold' : 'regular'}
                  tone={active ? 'primary' : 'tertiary'}
                  accessible={false}
                >
                  {entry.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <Screen>
        {screeningCase.sync.state === 'FAILED' ? (
          <InlineNotice
            tone="critical"
            title="This case has not been uploaded"
            message={
              screeningCase.sync.lastError ??
              'The last upload attempt failed. The case is safe on this device.'
            }
            actionLabel={syncing ? 'Retrying' : 'Retry upload'}
            onAction={handleRetrySync}
          />
        ) : null}

        {tab === 'SUMMARY' ? (
          <>
            {risk ? (
              <Panel
                tone={
                  risk.risk_level === 'LOW'
                    ? 'positive'
                    : risk.risk_level === 'REVIEW'
                      ? 'caution'
                      : 'critical'
                }
                style={{ marginTop: theme.spacing.lg }}
              >
                <Text role="label" tone="tertiary">
                  Assessment
                </Text>
                <View style={[styles.scoreRow, { marginTop: theme.spacing.sm }]}>
                  <Text role="headline">{risk.risk_score.toFixed(2)}</Text>
                  <RiskBadge level={risk.risk_level} />
                </View>
                {risk.bands ? (
                  <View style={{ marginTop: theme.spacing.lg }}>
                    <RiskMeter
                      score={risk.risk_score}
                      level={risk.risk_level}
                      bands={risk.bands}
                      animate={false}
                    />
                  </View>
                ) : null}
                <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
                  {risk.narrative}
                </Text>
              </Panel>
            ) : (
              <Panel style={{ marginTop: theme.spacing.lg }}>
                <Text role="subtitle">No risk assessment</Text>
                <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
                  Screening did not complete for this case. Any stages that did run are recorded
                  under Analysis.
                </Text>
              </Panel>
            )}

            {decision ? (
              <Section title="Officer decision">
                <Panel padded={false}>
                  <View style={{ padding: theme.spacing.lg }}>
                    <DecisionBadge decision={decision.decision} emphasis="solid" />
                  </View>
                  <KeyValueRow
                    label="Recorded by"
                    value={decision.officerName}
                    hint={formatDateTime(decision.decidedAt)}
                  />
                  <KeyValueRow
                    label="Assessment at decision"
                    value={
                      decision.riskLevelAtDecision
                        ? `${decision.riskLevelAtDecision} · ${(decision.riskScoreAtDecision ?? 0).toFixed(2)}`
                        : 'No assessment was produced'
                    }
                    hint="As shown to the officer at the time, not recomputed"
                  />
                  {decision.divergedFromRecommendation ? (
                    <KeyValueRow
                      label="Recommendation"
                      value="Officer decided differently"
                      hint="Recorded for later review"
                    />
                  ) : null}
                  {decision.remarks ? (
                    <KeyValueRow label="Remarks" value={decision.remarks} stacked />
                  ) : null}
                </Panel>
              </Section>
            ) : (
              <Section title="Officer decision">
                <Panel tone="caution">
                  <Text role="body" weight="medium">
                    No decision recorded
                  </Text>
                  <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
                    This case was screened but left open.
                  </Text>
                </Panel>
              </Section>
            )}

            <Section title="Case record">
              <Panel padded={false}>
                <KeyValueRow label="Reference" value={screeningCase.id} mono />
                <KeyValueRow
                  label="Document type"
                  value={documentTypeLabel(screeningCase.documentType)}
                />
                <KeyValueRow label="Officer" value={screeningCase.officerName} />
                <KeyValueRow
                  label="Post"
                  value={`${screeningCase.unit} · ${screeningCase.postName}`}
                />
                <KeyValueRow label="Opened" value={formatDateTime(screeningCase.createdAt)} />
                <KeyValueRow label="Last updated" value={formatDateTime(screeningCase.updatedAt)} />
              </Panel>
            </Section>

            <Section title="Status">
              <Panel>
                <View style={styles.badgeRow}>
                  <CaseStatusBadge status={screeningCase.status} />
                  <SyncBadge state={screeningCase.sync.state} />
                </View>
                <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.md }}>
                  {screeningCase.sync.state === 'SYNCED'
                    ? `Uploaded ${formatDateTime(screeningCase.sync.lastSyncedAt)}.`
                    : screeningCase.sync.state === 'FAILED'
                      ? `${screeningCase.sync.attempts} upload ${screeningCase.sync.attempts === 1 ? 'attempt has' : 'attempts have'} failed. The case remains on this device.`
                      : 'This case is held on this device and will be uploaded when a connection is available.'}
                </Text>
              </Panel>
            </Section>
          </>
        ) : null}

        {tab === 'DOCUMENT' ? (
          <>
            <Section title="Captures" style={{ marginTop: theme.spacing.lg }}>
              <View style={styles.captureRow}>
                {documentUri ? (
                  <CaptureThumb label="Document" uri={documentUri} aspectRatio={1.42} />
                ) : null}
                {personUri ? (
                  <CaptureThumb label="Subject" uri={personUri} aspectRatio={0.82} />
                ) : null}
              </View>
              {!documentUri && !personUri ? (
                <Panel>
                  <Text role="caption" tone="secondary">
                    The captures for this case are no longer on this device.
                  </Text>
                </Panel>
              ) : null}
            </Section>

            {caseResult && hasEvidence(caseResult.ocr) ? (
              <OcrDetails envelope={caseResult.ocr} result={caseResult.ocr.result} />
            ) : (
              <Section title="Document information">
                <Panel>
                  <Text role="caption" tone="secondary">
                    No information was extracted from this document.
                  </Text>
                </Panel>
              </Section>
            )}
          </>
        ) : null}

        {tab === 'ANALYSIS' ? (
          <>
            {!caseResult ? (
              <Section title="Analysis" style={{ marginTop: theme.spacing.lg }}>
                <Panel>
                  <Text role="caption" tone="secondary">
                    This case has no screening result. It was opened but never screened.
                  </Text>
                </Panel>
              </Section>
            ) : null}

            {caseResult && hasEvidence(caseResult.validation) ? (
              <ValidationDetails
                envelope={caseResult.validation}
                result={caseResult.validation.result}
              />
            ) : null}

            {caseResult && hasEvidence(caseResult.face_verification) && documentUri && personUri ? (
              <Section title="Face verification">
                <FaceDetails
                  envelope={caseResult.face_verification}
                  result={caseResult.face_verification.result}
                  documentImageUri={documentUri}
                  personImageUri={personUri}
                />
              </Section>
            ) : null}

            {caseResult && hasEvidence(caseResult.document_forensics) && documentUri ? (
              <Section title="Document forensics">
                <ForensicsDetails
                  envelope={caseResult.document_forensics}
                  result={caseResult.document_forensics.result}
                  documentImageUri={documentUri}
                  documentType={screeningCase.documentType}
                />
              </Section>
            ) : null}

            {caseResult ? (
              <Section title="Anomaly analysis">
                <AnomalyDetails
                  envelope={caseResult.anomaly}
                  documentImageUri={documentUri ?? ''}
                  documentType={screeningCase.documentType}
                />
              </Section>
            ) : null}

            <Section title="Pipeline record">
              <Panel padded={false}>
                {screeningCase.stages.map((stage, index) => (
                  <KeyValueRow
                    key={stage.id}
                    label={SCREENING_STAGE_DESCRIPTORS[stage.id].label}
                    value={stage.error ?? stage.detail ?? 'Did not run'}
                    stacked
                    hint={stage.completedAt ? formatDateTime(stage.completedAt) : undefined}
                    style={
                      index === 0
                        ? undefined
                        : {
                            borderTopWidth: theme.borderWidth.thin,
                            borderTopColor: theme.color.border,
                          }
                    }
                  />
                ))}
              </Panel>
            </Section>
          </>
        ) : null}

        {tab === 'AUDIT' ? (
          <Section title="Audit trail" style={{ marginTop: theme.spacing.lg }}>
            {audit.isLoading ? (
              <LoadingState label="Reading the audit trail" fill={false} />
            ) : (audit.data ?? []).length === 0 ? (
              <Panel>
                <Text role="caption" tone="secondary">
                  No events were recorded for this case.
                </Text>
              </Panel>
            ) : (
              <Panel>
                <EvidenceTimeline events={audit.data ?? []} showDates />
              </Panel>
            )}
          </Section>
        ) : null}

        <Button
          label="Back to cases"
          onPress={() => router.back()}
          variant="secondary"
          fullWidth
          style={{ marginTop: theme.spacing.xxl }}
        />
      </Screen>
    </>
  );
}

function CaptureThumb({
  label,
  uri,
  aspectRatio,
}: {
  label: string;
  uri: string;
  aspectRatio: number;
}) {
  const theme = useTheme();
  return (
    <View style={styles.capturePanel}>
      <Text role="label" tone="tertiary" style={{ marginBottom: theme.spacing.sm }}>
        {label}
      </Text>
      <View
        style={[
          styles.captureFrame,
          {
            aspectRatio,
            backgroundColor: theme.color.surfaceSunken,
            borderColor: theme.color.border,
            borderWidth: theme.borderWidth.thin,
            borderRadius: theme.radii.lg,
          },
        ]}
      >
        <Image
          source={{ uri }}
          style={StyleSheet.absoluteFill}
          contentFit="cover"
          transition={160}
          accessible
          accessibilityLabel={`${label} capture`}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  tabBar: {},
  tabRow: { flexDirection: 'row', gap: 20 },
  tab: {},
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  badgeRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  captureRow: { flexDirection: 'row', gap: 12 },
  capturePanel: { flex: 1, minWidth: 0 },
  captureFrame: { width: '100%', overflow: 'hidden' },
});
