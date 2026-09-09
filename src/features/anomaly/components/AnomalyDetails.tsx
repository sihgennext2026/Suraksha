import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { DocumentPreview, type PreviewRegion } from '@/components/data/DocumentPreview';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { useTheme } from '@/theme';
import type { AnomalyResult, DocumentType, Envelope } from '@/contracts';

interface AnomalyDetailsProps {
  envelope: Envelope<AnomalyResult>;
  documentImageUri: string;
  documentType: DocumentType;
}

/**
 * Anomaly analysis.
 *
 * PatchCore is not implemented, so in practice this screen renders the
 * unavailable state — and rendering it well matters more than the populated
 * case. An officer must be able to see that a check did not happen, and must
 * not be able to mistake its silence for a clean result. The populated branch
 * is written and typed so the module can be switched on without touching the
 * application.
 */
export function AnomalyDetails({
  envelope,
  documentImageUri,
  documentType,
}: AnomalyDetailsProps) {
  const theme = useTheme();
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const result = envelope.status === 'SUCCESS' || envelope.status === 'PARTIAL'
    ? envelope.result
    : null;

  const regions: PreviewRegion[] = useMemo(
    () =>
      (result?.suspicious_regions ?? []).map((region, index) => ({
        id: `anomaly-${index}`,
        box: region.bbox,
        severity: region.score,
        marker: String(index + 1),
        note: region.note ?? 'This region deviates from the reference distribution.',
        category: 'Deviation',
      })),
    [result],
  );

  if (!result) {
    return (
      <>
        <Panel style={{ marginTop: theme.spacing.lg }}>
          <View style={styles.verdictRow}>
            <Text role="title" weight="bold" tone="tertiary" accessible={false}>
              –
            </Text>
            <Text
              role="title"
              tone="secondary"
              accessibilityRole="header"
              accessibilityLabel="Anomaly analysis was not available for this screening."
            >
              NOT AVAILABLE
            </Text>
          </View>
          <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
            {envelope.errors[0]?.message ??
              'Anomaly analysis was not performed for this screening.'}
          </Text>
        </Panel>

        {/*
          Stated explicitly rather than left implied. A blank screen would read
          as "nothing was found"; this reads as "nothing was looked for".
        */}
        <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
          <Text role="label" tone="tertiary">
            What this means
          </Text>
          <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
            This check compares a document against a reference set of genuine documents to
            find deviations no tampering model was trained to recognise. It did not run, so
            it has produced neither a finding nor a clearance. The risk assessment excluded
            it rather than counting it either way.
          </Text>
        </Panel>

        <Section title="Analysis details">
          <Panel padded={false}>
            <KeyValueRow label="Status" value={envelope.status} mono />
            <KeyValueRow label="Reason" value={envelope.errors[0]?.code ?? '—'} mono />
          </Panel>
        </Section>
      </>
    );
  }

  const anomalous = result.anomalous;
  const tone = anomalous ? 'caution' : 'positive';
  const colour = anomalous ? theme.color.caution : theme.color.positive;

  return (
    <>
      <Panel tone={tone} style={{ marginTop: theme.spacing.lg }}>
        <View style={styles.verdictRow}>
          <Text role="title" weight="bold" style={{ color: colour }} accessible={false}>
            {anomalous ? '!' : '✓'}
          </Text>
          <Text role="title" style={{ color: colour }} accessibilityRole="header">
            {anomalous ? 'DEVIATION DETECTED' : 'WITHIN EXPECTED RANGE'}
          </Text>
        </View>

        <View style={{ marginTop: theme.spacing.lg }}>
          <Text role="label" tone="tertiary">
            Anomaly score
          </Text>
          <Text role="headline" style={{ color: colour, marginTop: 2 }}>
            {result.anomaly_score.toFixed(2)}
          </Text>
          {result.threshold != null ? (
            <Text role="caption" tone="tertiary" style={{ marginTop: 2 }}>
              Threshold {result.threshold.toFixed(2)}
            </Text>
          ) : null}
        </View>
      </Panel>

      <Section title="Where">
        <DocumentPreview
          uri={documentImageUri}
          aspectRatio={DOCUMENT_TYPE_DESCRIPTORS[documentType].captureAspectRatio}
          regions={regions}
          selectedRegionId={selectedRegion}
          onSelectRegion={setSelectedRegion}
          accessibilityLabel="Captured document with anomalous regions marked"
        />
      </Section>

      <Section title="Analysis details">
        <Panel padded={false}>
          <KeyValueRow label="Model" value={envelope.model_version} mono />
          <KeyValueRow label="Status" value={envelope.status} mono />
          {result.reference_set_size != null ? (
            <KeyValueRow
              label="Reference set"
              value={`${result.reference_set_size} documents`}
              mono
            />
          ) : null}
        </Panel>
      </Section>
    </>
  );
}

const styles = StyleSheet.create({
  verdictRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});
