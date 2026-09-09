import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { DocumentPreview, type PreviewRegion } from '@/components/data/DocumentPreview';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { MANIPULATION_TYPE_LABELS } from '@/constants/labels';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { THRESHOLD_CONFIDENCE_NOTES } from '@/config/thresholds';
import { useTheme } from '@/theme';
import type { DocumentForensicsResult, DocumentType, Envelope } from '@/contracts';

interface ForensicsDetailsProps {
  envelope: Envelope<DocumentForensicsResult>;
  result: DocumentForensicsResult;
  documentImageUri: string;
  documentType: DocumentType;
  showProvenance?: boolean;
}

/**
 * Document forensics.
 *
 * The wording throughout is evidence-oriented. The model reports a pattern it
 * recognised in an image; it does not know whether a document is genuine, and
 * saying so would hand the officer a verdict dressed as a fact. So the screen
 * says "potential tampering detected" and "suspicious region identified", and
 * leaves the conclusion where it belongs.
 *
 * The other thing this screen has to get right is an empty region list. The
 * classification head can fire while the localisation head resolves nothing —
 * which is a PARTIAL result, not a clean one — and an officer who reads "no
 * regions" as "nothing found" would draw exactly the wrong conclusion.
 */
export function ForensicsDetails({
  envelope,
  result,
  documentImageUri,
  documentType,
  showProvenance = true,
}: ForensicsDetailsProps) {
  const theme = useTheme();
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

  const tampered = result.tampered;
  const verdictColour = tampered ? theme.color.critical : theme.color.positive;
  const tone = tampered ? 'critical' : 'positive';

  const regions: PreviewRegion[] = useMemo(
    () =>
      result.suspicious_regions.map((region, index) => ({
        id: `region-${index}`,
        box: region.bbox,
        severity: region.score,
        marker: String(index + 1),
        note: region.note ?? 'This region contributed to the finding.',
        category: MANIPULATION_TYPE_LABELS[result.manipulation_type],
      })),
    [result.suspicious_regions, result.manipulation_type],
  );

  const localisationInconclusive = tampered && regions.length === 0;

  return (
    <>
      <Panel tone={tone} style={{ marginTop: theme.spacing.lg }}>
        <View style={styles.verdictRow}>
          <Text role="title" weight="bold" style={{ color: verdictColour }} accessible={false}>
            {tampered ? '✕' : '✓'}
          </Text>
          <Text
            role="title"
            style={{ color: verdictColour }}
            accessibilityRole="header"
            accessibilityLabel={
              tampered
                ? 'Potential tampering detected. Officer review required.'
                : 'No tampering indicators found.'
            }
          >
            {tampered ? 'POTENTIAL TAMPERING DETECTED' : 'NO TAMPERING DETECTED'}
          </Text>
        </View>

        <View style={[styles.metricRow, { marginTop: theme.spacing.lg }]}>
          <View style={styles.metric}>
            <Text role="label" tone="tertiary">
              Tamper score
            </Text>
            <Text role="headline" style={{ color: verdictColour, marginTop: 2 }}>
              {result.tamper_score.toFixed(2)}
            </Text>
          </View>
          {tampered ? (
            <View style={styles.metric}>
              <Text role="label" tone="tertiary">
                Type
              </Text>
              <Text role="subtitle" style={{ marginTop: 4 }}>
                {MANIPULATION_TYPE_LABELS[result.manipulation_type]}
              </Text>
              {result.type_score != null ? (
                <Text role="monoSmall" tone="tertiary" style={{ marginTop: 2 }}>
                  type score {result.type_score.toFixed(2)}
                </Text>
              ) : null}
            </View>
          ) : null}
        </View>

        <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
          {tampered
            ? 'The document shows characteristics consistent with manipulation. This is ' +
              'evidence for you to weigh against the document in front of you — it is not ' +
              'a determination that the document is false.'
            : 'No manipulation pattern the model recognises was found in this document. ' +
              'That is not proof of authenticity: a technique the model has not seen would ' +
              'not appear here.'}
        </Text>
      </Panel>

      {localisationInconclusive ? (
        <Panel tone="caution" style={{ marginTop: theme.spacing.md }}>
          <Text role="body" weight="semibold" tone="caution">
            No region could be localised
          </Text>
          <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
            Tampering was detected but could not be traced to a specific area of the
            document. The absence of a highlighted region is not evidence that the document
            is sound — examine it in full.
          </Text>
        </Panel>
      ) : null}

      <Section
        title="Where"
        description={
          regions.length > 0
            ? 'Regions the model flagged, drawn on the capture. Tap one to read the finding.'
            : tampered
              ? 'No region could be localised.'
              : 'No region of this document was flagged.'
        }
      >
        <DocumentPreview
          uri={documentImageUri}
          aspectRatio={DOCUMENT_TYPE_DESCRIPTORS[documentType].captureAspectRatio}
          regions={regions}
          selectedRegionId={selectedRegion}
          onSelectRegion={setSelectedRegion}
          accessibilityLabel="Captured document with forensic findings marked"
        />
      </Section>

      {regions.length > 0 ? (
        <Section title="Findings">
          <Panel padded={false}>
            {regions.map((region, index) => (
              <KeyValueRow
                key={region.id}
                label={`Region ${region.marker}`}
                value={region.note}
                stacked
                hint={`Region score ${region.severity.toFixed(2)}`}
                onPress={() => setSelectedRegion(region.id)}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              />
            ))}
          </Panel>
        </Section>
      ) : null}

      {showProvenance ? (
        <Section title="Analysis details">
          <Panel padded={false}>
            <KeyValueRow label="Model" value={envelope.model_version} mono />
            <KeyValueRow label="Status" value={envelope.status} mono />
            <KeyValueRow
              label="Regions localised"
              value={String(result.suspicious_regions.length)}
              mono
            />
          </Panel>

          <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
            <Text role="label" tone="tertiary">
              About this model
            </Text>
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
              Tamper detection recognises manipulation patterns it has been trained on. A
              document altered by a technique outside that set can score low here.
            </Text>
            <Text role="caption" tone="caution" style={{ marginTop: theme.spacing.sm }}>
              {THRESHOLD_CONFIDENCE_NOTES.forensics}
            </Text>
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  verdictRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  metricRow: { flexDirection: 'row', gap: 32 },
  metric: { flexShrink: 1 },
});
