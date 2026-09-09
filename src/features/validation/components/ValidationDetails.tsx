import React from 'react';
import { StyleSheet, View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { ValidationDecisionBadge } from '@/components/data/StatusBadge';
import { ValidationRow } from '@/components/data/ValidationRow';
import { useTheme } from '@/theme';
import type { Envelope, ValidationResult } from '@/contracts';

interface ValidationDetailsProps {
  envelope: Envelope<ValidationResult>;
  result: ValidationResult;
  showProvenance?: boolean;
}

/**
 * Deterministic rule results.
 *
 * Presented explicitly as rule checking rather than analysis: no confidence, no
 * probability, and no model named anywhere on this screen. The one sentence
 * that matters most is the disclaimer — a rule failure is a rule failure, not a
 * finding that the document is false — because an officer reading five red
 * crosses will otherwise draw that conclusion for themselves.
 *
 * The tally splits five ways rather than three. `Not applicable` and `not
 * evaluated` are counted separately from failures and from each other, so an
 * officer can tell a rule that did not apply from one whose input was missing.
 */
export function ValidationDetails({
  envelope,
  result,
  showProvenance = true,
}: ValidationDetailsProps) {
  const theme = useTheme();

  const evaluated = result.checks.filter(
    (check) => check.status === 'PASS' || check.status === 'FAIL' || check.status === 'REVIEW',
  );
  const notEvaluated = result.checks.filter(
    (check) => check.status === 'NOT_APPLICABLE' || check.status === 'NOT_AVAILABLE',
  );

  return (
    <>
      <Panel style={{ marginTop: theme.spacing.lg }}>
        <View style={styles.headerRow}>
          <Text role="label" tone="tertiary">
            Rule checking
          </Text>
          <ValidationDecisionBadge decision={result.decision} />
        </View>

        <View style={[styles.tally, { marginTop: theme.spacing.md }]}>
          <Tally label="Passed" value={result.summary.passed} colour={theme.color.positive} />
          <Tally label="Failed" value={result.summary.failed} colour={theme.color.critical} />
          <Tally
            label="Inconclusive"
            value={result.summary.review}
            colour={theme.color.caution}
          />
          <Tally
            label="Not evaluated"
            value={result.summary.not_applicable + result.summary.not_available}
            colour={theme.color.textTertiary}
          />
        </View>

        <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
          These checks are arithmetic and comparison over the extracted values. No model is
          involved, and the same document always produces the same result — you can
          reproduce any of them by hand from the document itself.
        </Text>
        <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.sm }}>
          A failed rule is evidence to weigh, not a finding that the document is false. A
          misread character produces the same failure as an alteration.
        </Text>
      </Panel>

      <Section title={`Rules evaluated (${evaluated.length})`}>
        {evaluated.length === 0 ? (
          <Panel>
            <Text role="caption" tone="secondary">
              No rule could be evaluated against this document.
            </Text>
          </Panel>
        ) : (
          <Panel padded={false}>
            {evaluated.map((check, index) => (
              <View
                key={`${check.rule_id}-${index}`}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              >
                <ValidationRow check={check} defaultExpanded={check.status === 'FAIL'} />
              </View>
            ))}
          </Panel>
        )}
      </Section>

      {notEvaluated.length > 0 ? (
        <Section
          title={`Not evaluated (${notEvaluated.length})`}
          description="Rules that did not apply to this document, or whose input was missing. Neither counts as a failure."
        >
          <Panel padded={false}>
            {notEvaluated.map((check, index) => (
              <View
                key={`${check.rule_id}-${index}`}
                style={
                  index === 0
                    ? undefined
                    : { borderTopWidth: theme.borderWidth.thin, borderTopColor: theme.color.border }
                }
              >
                <ValidationRow check={check} />
              </View>
            ))}
          </Panel>
        </Section>
      ) : null}

      {showProvenance ? (
        <Section title="Analysis details">
          <Panel padded={false}>
            <KeyValueRow label="Method" value="Deterministic rule engine" />
            <KeyValueRow label="Ruleset version" value={result.rule_version} mono />
            <KeyValueRow label="Status" value={envelope.status} mono />
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

function Tally({ label, value, colour }: { label: string; value: number; colour: string }) {
  const theme = useTheme();
  return (
    <View
      style={styles.tallyItem}
      accessible
      accessibilityLabel={`${value} ${label.toLowerCase()}`}
    >
      <Text role="title" style={{ color: colour }} accessible={false}>
        {value}
      </Text>
      <Text
        role="caption"
        tone="tertiary"
        style={{ marginTop: theme.spacing.xxs }}
        accessible={false}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  tally: { flexDirection: 'row', flexWrap: 'wrap', gap: 24 },
  tallyItem: { minWidth: 68 },
});
