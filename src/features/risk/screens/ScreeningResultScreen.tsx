import React, { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { EvidenceCard } from '@/components/data/EvidenceCard';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { RiskBadge } from '@/components/data/StatusBadge';
import { RiskMeter } from '@/components/data/RiskMeter';
import { BottomSheet, ConfirmDialog } from '@/components/overlay/Sheet';
import { ErrorState } from '@/components/feedback/States';
import { RISK_LEVEL_PRESENTATION } from '@/constants/labels';
import { ROUTES } from '@/constants/routes';
import { THRESHOLD_CONFIDENCE_NOTES } from '@/config/thresholds';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useTheme } from '@/theme';
import { hasEvidence, type ModuleName } from '@/contracts';

/**
 * The screening result.
 *
 * Everything on this screen was decided by the fusion engine and arrived in the
 * case document: the band, the score, the ranked contributors, the evidence
 * index. The application ranks nothing, interprets nothing and computes nothing
 * here — which is what stops it drifting from the engine that will eventually
 * run on a server.
 *
 * The result is decision support and says so. The primary action is "review the
 * evidence", not "accept", because the officer's job at this point is to look.
 */
export function ScreeningResultScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('RESULTS');

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [confirmExit, setConfirmExit] = useState(false);

  const openModule = useCallback(
    (module: ModuleName) => {
      const route: Partial<Record<ModuleName, string>> = {
        ocr: ROUTES.screening.ocr,
        validation: ROUTES.screening.validation,
        face_verification: ROUTES.screening.face,
        document_forensics: ROUTES.screening.forensics,
        anomaly: ROUTES.screening.anomaly,
      };
      const target = route[module];
      if (target) router.push(target);
    },
    [router],
  );

  if (!activeCase?.result) return null;
  const caseResult = activeCase.result;

  // The fusion engine itself can fail. When it does the module findings are
  // still there to be read, so the officer is offered them rather than a dead
  // end — the decision is theirs to make either way.
  if (!hasEvidence(caseResult.risk)) {
    return (
      <>
        <AppHeader title="Screening result" subtitle={activeCase.id} />
        <Screen
          footer={
            <Button
              label="Review the evidence"
              onPress={() => router.push(ROUTES.screening.evidence)}
              fullWidth
            />
          }
        >
          <ErrorState
            title="No risk assessment was produced"
            message={
              caseResult.risk.errors[0]?.message ??
              'The assessment could not be produced. Every module finding is still ' +
                'available, so record your decision on those.'
            }
          />
        </Screen>
      </>
    );
  }

  const risk = caseResult.risk.result;
  const presentation = RISK_LEVEL_PRESENTATION[risk.risk_level];
  const levelColour = {
    LOW: theme.color.positive,
    REVIEW: theme.color.caution,
    HIGH: theme.color.critical,
  }[risk.risk_level];

  const counted = risk.contributors.filter((entry) => entry.counted);
  const adverse = counted.filter((entry) => entry.severity !== 'NONE');
  const excluded = risk.contributors.filter((entry) => !entry.counted);

  return (
    <>
      <AppHeader
        title="Screening result"
        subtitle={activeCase.id}
        onBack={() => setConfirmExit(true)}
        backLabel="Leave without recording a decision"
        right={<RiskBadge level={risk.risk_level} size="small" />}
      />

      <Screen
        footer={
          <View style={styles.footer}>
            <Button
              label="Evidence"
              onPress={() => router.push(ROUTES.screening.evidence)}
              variant="secondary"
              style={styles.footerSecondary}
            />
            <Button
              label="Record decision"
              onPress={() => router.push(ROUTES.screening.decision)}
              style={styles.footerPrimary}
              haptic
              testID="result-record-decision"
            />
          </View>
        }
      >
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
          <View style={styles.verdictRow}>
            <Text role="title" weight="bold" style={{ color: levelColour }} accessible={false}>
              {presentation.glyph}
            </Text>
            <Text
              role="headline"
              style={{ color: levelColour }}
              accessibilityRole="header"
              accessibilityLabel={`Assessment: ${presentation.a11yLabel}`}
            >
              {presentation.label.toUpperCase()}
            </Text>
          </View>

          <View style={[styles.scoreRow, { marginTop: theme.spacing.lg }]}>
            <Text role="metric" style={{ color: levelColour }} accessible={false}>
              {risk.risk_score.toFixed(2)}
            </Text>
            <Text role="title" tone="secondary" accessible={false}>
              fused score
            </Text>
          </View>

          {risk.bands ? (
            <View style={{ marginTop: theme.spacing.lg }}>
              <RiskMeter
                score={risk.risk_score}
                level={risk.risk_level}
                bands={risk.bands}
              />
            </View>
          ) : null}
        </Panel>

        {/*
          Coverage is shown whenever a module was missing. An officer reading a
          LOW band needs to know how much was actually examined to produce it.
        */}
        {risk.evidence_coverage < 1 ? (
          <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
            <Text role="label" tone="tertiary">
              Evidence coverage
            </Text>
            <Text role="body" style={{ marginTop: theme.spacing.xs }}>
              {Math.round(risk.evidence_coverage * 100)}% of the checks produced a result
            </Text>
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
              The checks that did not run were excluded from the assessment rather than
              counted for or against this document.
            </Text>
          </Panel>
        ) : null}

        <Section title="Assessment">
          <Panel>
            <Text role="bodyLarge" tone="secondary">
              {risk.narrative}
            </Text>
            <View
              style={{
                marginTop: theme.spacing.lg,
                paddingTop: theme.spacing.lg,
                borderTopWidth: theme.borderWidth.thin,
                borderTopColor: theme.color.border,
              }}
            >
              <Text role="caption" tone="tertiary">
                This is decision support. The operational decision is yours to make and is
                recorded against your name.
              </Text>
            </View>
          </Panel>
        </Section>

        {risk.escalations && risk.escalations.length > 0 ? (
          <Section
            title="Why this band"
            description="Rules that raised the assessment above its fused score."
          >
            <Panel>
              {risk.escalations.map((reason, index) => (
                <Text
                  key={index}
                  role="caption"
                  tone="secondary"
                  style={{ marginTop: index === 0 ? 0 : theme.spacing.sm }}
                >
                  · {reason}
                </Text>
              ))}
            </Panel>
          </Section>
        ) : null}

        {adverse.length > 0 ? (
          <Section
            title="Primary contributors"
            description="Ranked by the fusion engine, highest impact first."
          >
            <Panel padded={false}>
              {adverse.map((factor, index) => (
                <View
                  key={`${factor.source}-${index}`}
                  accessible
                  accessibilityRole="text"
                  accessibilityLabel={`Contributor ${index + 1}. ${factor.signal}. ${factor.impact}`}
                  style={[
                    styles.factorRow,
                    {
                      padding: theme.spacing.lg,
                      borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                      borderTopColor: theme.color.border,
                    },
                  ]}
                >
                  <Text role="mono" tone="tertiary" style={styles.factorIndex} accessible={false}>
                    {index + 1}
                  </Text>
                  <View style={styles.factorBody}>
                    <Text role="body" weight="medium" accessible={false}>
                      {factor.signal.replace(/_/g, ' ')}
                    </Text>
                    <Text
                      role="caption"
                      tone="secondary"
                      style={{ marginTop: 2 }}
                      accessible={false}
                    >
                      {factor.impact}
                    </Text>
                  </View>
                  <Text role="monoSmall" tone="tertiary" accessible={false}>
                    {factor.weight != null ? factor.weight.toFixed(2) : '—'}
                  </Text>
                </View>
              ))}
            </Panel>
          </Section>
        ) : null}

        {excluded.length > 0 ? (
          <Section
            title="Not counted"
            description="Checks that produced no result. Neither a pass nor a failure."
          >
            <Panel padded={false}>
              {excluded.map((factor, index) => (
                <KeyValueRow
                  key={`${factor.source}-${index}`}
                  label={factor.source.replace(/_/g, ' ')}
                  value={factor.impact}
                  stacked
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
        ) : null}

        <Section title="Evidence" description="Tap any check to see its full findings.">
          <Panel padded={false}>
            {caseResult.evidence.map((item, index) => (
              <View
                key={item.module}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              >
                <EvidenceCard item={item} onPress={() => openModule(item.module)} />
              </View>
            ))}
          </Panel>
        </Section>

        <Button
          label="Analysis details"
          onPress={() => setDetailsOpen(true)}
          variant="ghost"
          size="medium"
          style={{ marginTop: theme.spacing.lg, alignSelf: 'flex-start' }}
        />
      </Screen>

      <BottomSheet
        visible={detailsOpen}
        onDismiss={() => setDetailsOpen(false)}
        title="Analysis details"
        description="How this assessment was produced."
      >
        <Panel padded={false} style={{ marginBottom: theme.spacing.lg }}>
          <KeyValueRow label="Engine" value={risk.engine_version} mono />
          <KeyValueRow label="Method" value="Deterministic weighted fusion" />
          <KeyValueRow label="Configuration" value={risk.config_version ?? '—'} mono />
          <KeyValueRow
            label="Evidence coverage"
            value={`${Math.round(risk.evidence_coverage * 100)}%`}
            mono
          />
          <KeyValueRow label="Contract" value={caseResult.schema_version} mono />
        </Panel>

        <Text role="caption" tone="caution" style={{ marginBottom: theme.spacing.xl }}>
          {THRESHOLD_CONFIDENCE_NOTES.risk}
        </Text>
      </BottomSheet>

      <ConfirmDialog
        visible={confirmExit}
        title="Leave without a decision?"
        message={`Case ${activeCase.id} keeps its findings and stays open. It will appear on the dashboard as awaiting a decision.`}
        confirmLabel="Leave open"
        onConfirm={() => {
          setConfirmExit(false);
          router.replace(ROUTES.app.dashboard);
        }}
        cancelLabel="Stay"
        onCancel={() => setConfirmExit(false)}
      />
    </>
  );
}

const styles = StyleSheet.create({
  verdictRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  scoreRow: { flexDirection: 'row', alignItems: 'baseline', gap: 10 },
  factorRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  factorIndex: { width: 14 },
  factorBody: { flex: 1, minWidth: 0 },
  footer: { flexDirection: 'row', gap: 8 },
  footerSecondary: { flexShrink: 0 },
  footerPrimary: { flex: 1 },
});
