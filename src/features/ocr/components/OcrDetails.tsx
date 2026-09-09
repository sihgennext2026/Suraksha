import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { ConfidenceIndicator } from '@/components/data/ConfidenceIndicator';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { ModuleStatusBadge } from '@/components/data/StatusBadge';
import { OCR_THRESHOLDS } from '@/config/thresholds';
import { useTheme } from '@/theme';
import type { Envelope, OcrField, OcrResult } from '@/contracts';
import { formatDate } from '@/utils/date';
import { groupMrzLine } from '@/utils/format';

interface OcrDetailsProps {
  envelope: Envelope<OcrResult>;
  result: OcrResult;
  showProvenance?: boolean;
}

const DATE_KEYS = new Set(['date_of_birth', 'date_of_issue', 'date_of_expiry']);
const MONO_KEYS = new Set([
  'passport_number',
  'document_number',
  'id_number',
  'license_number',
  'personal_number',
  'nationality',
  'issuing_state',
  'sex',
]);

/**
 * Extracted document information.
 *
 * Two things here are load-bearing. Values are stacked under their labels
 * rather than right-aligned, because an officer reads these back against the
 * document in their hand and a wrapped value is far harder to check than a
 * stacked one. And a field the extractor did not find is shown as *not found* —
 * never as an empty string, and never omitted, because an absent field and a
 * blank one mean different things to the person holding the document.
 *
 * Per-field OCR confidence is a genuine model output on a 0..1 scale, so it is
 * rendered as a percentage. That is not a rescaling: it is what the recogniser
 * reports.
 */
export function OcrDetails({ envelope, result, showProvenance = true }: OcrDetailsProps) {
  const theme = useTheme();
  const [showRawMrz, setShowRawMrz] = useState(false);

  const populated = result.fields.filter((field) => field.value);
  const missing = result.fields.filter((field) => !field.value);

  const confidence = result.overall_confidence;
  const lowConfidence =
    confidence !== null && confidence < OCR_THRESHOLDS.reviewConfidenceBelow;

  return (
    <>
      <Panel style={{ marginTop: theme.spacing.lg }}>
        <View style={styles.summaryRow}>
          <View style={styles.summaryText}>
            <Text role="label" tone="tertiary">
              Extraction confidence
            </Text>
            <Text role="title" style={{ marginTop: theme.spacing.xxs }}>
              {confidence === null ? 'Not reported' : `${Math.round(confidence * 100)}%`}
            </Text>
          </View>
          {confidence !== null ? (
            <ConfidenceIndicator
              value={confidence}
              width={72}
              showValue={false}
              label="Overall extraction confidence"
            />
          ) : null}
        </View>
        <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.md }}>
          {populated.length} of {result.fields.length} fields were read from this document.
          {lowConfidence
            ? ' Confidence is below the usual range — verify each value against the document by eye.'
            : ''}
        </Text>
      </Panel>

      <Section title="Document information">
        {populated.length === 0 ? (
          <Panel>
            <Text role="caption" tone="secondary">
              No fields were read from this document.
            </Text>
          </Panel>
        ) : (
          <Panel padded={false}>
            {populated.map((field, index) => (
              <View
                key={field.key}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              >
                <KeyValueRow
                  label={fieldLabel(field.key)}
                  value={
                    DATE_KEYS.has(field.key) && field.value
                      ? formatDate(field.value)
                      : (field.value ?? '')
                  }
                  mono={MONO_KEYS.has(field.key)}
                  stacked
                  hint={sourceHint(field)}
                  trailing={
                    field.confidence != null ? (
                      <ConfidenceIndicator
                        value={field.confidence}
                        width={44}
                        label={`${fieldLabel(field.key)} confidence`}
                      />
                    ) : undefined
                  }
                />
              </View>
            ))}
          </Panel>
        )}

        {missing.length > 0 ? (
          <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
            <Text role="label" tone="tertiary">
              Not found on this document
            </Text>
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
              {missing.map((field) => fieldLabel(field.key)).join(', ')}
            </Text>
            <Text role="caption" tone="tertiary" style={{ marginTop: theme.spacing.xs }}>
              A field the extractor could not locate is left empty rather than guessed.
            </Text>
          </Panel>
        ) : null}
      </Section>

      <Section title="Machine-readable zone">
        <Panel>
          <View style={styles.mrzHeader}>
            <View style={styles.summaryText}>
              <Text role="subtitle">
                {!result.mrz.present
                  ? 'No zone on this document'
                  : result.mrz.checksum_valid === null
                    ? 'Read, not yet checked'
                    : result.mrz.checksum_valid
                      ? 'Checksum passed'
                      : 'Checksum failed'}
              </Text>
              {result.mrz.present ? (
                <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xxs }}>
                  {result.mrz.format} format · {result.mrz.lines.length} lines
                </Text>
              ) : null}
            </View>
          </View>

          {result.mrz.present ? (
            <>
              <View
                style={[
                  {
                    marginTop: theme.spacing.lg,
                    backgroundColor: theme.color.surfaceSunken,
                    borderColor: theme.color.border,
                    borderWidth: theme.borderWidth.thin,
                    borderRadius: theme.radii.md,
                    padding: theme.spacing.md,
                  },
                ]}
              >
                {result.mrz.lines.map((line, index) => (
                  <Text
                    key={index}
                    role="monoSmall"
                    tone="secondary"
                    accessibilityLabel={`Machine-readable zone line ${index + 1}`}
                    style={{ marginTop: index === 0 ? 0 : theme.spacing.xs }}
                  >
                    {showRawMrz ? line : groupMrzLine(line).join(' ')}
                  </Text>
                ))}
              </View>

              <Pressable
                onPress={() => setShowRawMrz((current) => !current)}
                accessibilityRole="button"
                accessibilityLabel={
                  showRawMrz ? 'Show the zone in groups' : 'Show the zone exactly as read'
                }
                hitSlop={8}
                style={{ marginTop: theme.spacing.sm, alignSelf: 'flex-start' }}
              >
                <Text role="caption" tone="accent" weight="semibold">
                  {showRawMrz ? 'Show grouped' : 'Show exactly as read'}
                </Text>
              </Pressable>

              {result.mrz.check_digits.length > 0 ? (
                <>
                  <Text role="label" tone="tertiary" style={{ marginTop: theme.spacing.xl }}>
                    Check digits
                  </Text>
                  <View style={{ marginTop: theme.spacing.sm }}>
                    {result.mrz.check_digits.map((digit) => (
                      <View
                        key={digit.field}
                        accessible
                        accessibilityRole="text"
                        accessibilityLabel={`${digit.field} check digit ${
                          digit.valid
                            ? 'valid'
                            : `invalid, read ${digit.observed}, expected ${digit.computed}`
                        }`}
                        style={[styles.digitRow, { marginTop: theme.spacing.xs }]}
                      >
                        <Text
                          role="monoSmall"
                          weight="bold"
                          style={{
                            color: digit.valid ? theme.color.positive : theme.color.critical,
                            width: 12,
                          }}
                          accessible={false}
                        >
                          {digit.valid ? '✓' : '✕'}
                        </Text>
                        <Text
                          role="caption"
                          tone="secondary"
                          style={styles.digitLabel}
                          accessible={false}
                        >
                          {digit.field}
                        </Text>
                        <Text
                          role="monoSmall"
                          tone={digit.valid ? 'tertiary' : 'critical'}
                          accessible={false}
                        >
                          {digit.valid ? digit.observed : `${digit.observed} ≠ ${digit.computed}`}
                        </Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : (
                /*
                  Extraction reads the zone; the checksum is verified by rule
                  validation. "Not yet checked" is deliberately distinct from a
                  failed check.
                */
                <Panel tone="sunken" style={{ marginTop: theme.spacing.lg }}>
                  <Text role="caption" tone="secondary">
                    The zone was read but its check digits are verified by rule validation,
                    not by extraction. See the validation findings for the checksum result.
                  </Text>
                </Panel>
              )}
            </>
          ) : (
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.md }}>
              This document type does not carry a machine-readable zone, so no checksum
              applies to it.
            </Text>
          )}
        </Panel>
      </Section>

      {showProvenance ? (
        <Section title="Analysis details">
          <Panel padded={false}>
            <KeyValueRow label="Engine" value={envelope.model_version} mono />
            <KeyValueRow label="Status" value={envelope.status} mono />
            <KeyValueRow
              label="Document located"
              value={result.detection.detected ? 'Yes' : 'No'}
            />
            {result.language ? (
              <KeyValueRow label="Script" value={result.language.toUpperCase()} mono />
            ) : null}
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

/** `date_of_birth` reads as `Date of birth`. */
function fieldLabel(key: string): string {
  const words = key.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Provenance matters to an officer: a value lifted from a checksummed MRZ is
 * more trustworthy than one matched heuristically against a printed label.
 */
function sourceHint(field: OcrField): string | undefined {
  return {
    mrz: 'From the machine-readable zone',
    label_same_line: 'Matched to a printed label',
    label_next_line: 'Matched to a printed label',
    standalone_id: 'Read as a standalone identifier',
    not_found: undefined,
  }[field.source];
}

const styles = StyleSheet.create({
  summaryRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  summaryText: { flex: 1, minWidth: 0 },
  mrzHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 },
  digitRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  digitLabel: { flex: 1 },
});

export { ModuleStatusBadge };
