import React, { useCallback } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { EvidenceCard } from '@/components/data/EvidenceCard';
import { EvidenceTimeline } from '@/components/data/EvidenceTimeline';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { EmptyState, LoadingState } from '@/components/feedback/States';
import { documentTypeLabel } from '@/constants/documents';
import { ROUTES } from '@/constants/routes';
import { SCREENING_STAGE_DESCRIPTORS } from '@/constants/screening';
import { useCaseAudit } from '@/features/cases/useCases';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useTheme } from '@/theme';
import type { ModuleName } from '@/contracts';
import { formatDateTime } from '@/utils/date';

/**
 * Evidence review.
 *
 * The one screen that gathers everything the screening produced in one place:
 * both captures, every stage's finding, and the audit trail as it stands. An
 * officer about to record a decision they may have to defend needs to be able
 * to see the whole record without navigating between six screens to assemble it.
 */
export function EvidenceScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('CASE');
  const audit = useCaseAudit(activeCase?.id);

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

  if (!activeCase) return null;

  const caseResult = activeCase.result;
  const settledStages = activeCase.stages.filter((stage) => stage.status !== 'WAITING');

  return (
    <>
      <AppHeader
        title="Evidence"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />

      <Screen
        footer={
          <Button
            label="Record decision"
            onPress={() => router.push(ROUTES.screening.decision)}
            fullWidth
            haptic
          />
        }
      >
        <Section title="Captures">
          <View style={styles.captureRow}>
            {activeCase.document ? (
              <CapturePanel
                label="Document"
                uri={activeCase.document.image.uri}
                caption={documentTypeLabel(activeCase.documentType)}
                aspectRatio={1.42}
              />
            ) : null}
            {activeCase.person ? (
              <CapturePanel
                label="Subject"
                uri={activeCase.person.image.uri}
                caption={formatDateTime(activeCase.person.image.capturedAt)}
                aspectRatio={0.82}
              />
            ) : null}
          </View>
        </Section>

        {caseResult ? (
          <Section title="Findings" description="Tap a check to see its full analysis.">
            <Panel padded={false}>
              {caseResult.evidence.map((item, index) => (
                <View
                  key={item.module}
                  style={
                    index === 0
                      ? undefined
                      : {
                          borderTopWidth: theme.borderWidth.thin,
                          borderTopColor: theme.color.border,
                        }
                  }
                >
                  <EvidenceCard item={item} onPress={() => openModule(item.module)} />
                </View>
              ))}
            </Panel>
          </Section>
        ) : (
          <Section title="Findings">
            <Panel>
              <EmptyState
                title="Screening has not run"
                message="No findings have been produced for this case yet. The stages that did complete are listed below."
              />
            </Panel>
          </Section>
        )}

        <Section title="Pipeline record" description="What each stage concluded, and when.">
          <Panel padded={false}>
            {settledStages.map((stage, index) => (
              <KeyValueRow
                key={stage.id}
                label={SCREENING_STAGE_DESCRIPTORS[stage.id].label}
                value={stage.error ?? stage.detail ?? '—'}
                stacked
                hint={stage.completedAt ? formatDateTime(stage.completedAt) : undefined}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              />
            ))}
          </Panel>
        </Section>

        <Section title="Audit trail" description="Every recorded event for this case, in order.">
          {audit.isLoading ? (
            <LoadingState label="Reading the audit trail" fill={false} />
          ) : (audit.data ?? []).length === 0 ? (
            <Panel>
              <Text role="caption" tone="secondary">
                No events have been recorded for this case yet.
              </Text>
            </Panel>
          ) : (
            <Panel>
              <EvidenceTimeline events={audit.data ?? []} />
            </Panel>
          )}
        </Section>
      </Screen>
    </>
  );
}

function CapturePanel({
  label,
  uri,
  caption,
  aspectRatio,
}: {
  label: string;
  uri: string;
  caption: string;
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
      <Text role="caption" tone="tertiary" style={{ marginTop: theme.spacing.xs }}>
        {caption}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  captureRow: { flexDirection: 'row', gap: 12 },
  capturePanel: { flex: 1, minWidth: 0 },
  captureFrame: { width: '100%', overflow: 'hidden' },
});
