import React, { memo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

import { Text } from '@/components/primitives/Text';
import { VALIDATION_STATUS_PRESENTATION } from '@/constants/labels';
import { useTheme } from '@/theme';
import type { ValidationCheck } from '@/contracts';

interface ValidationRowProps {
  check: ValidationCheck;
  /** Expanded on first render. Used to open failing rules automatically. */
  defaultExpanded?: boolean;
}

/**
 * One deterministic rule, expandable to its full reasoning.
 *
 * Five statuses are rendered distinctly, and the two that are not failures are
 * the ones that matter most here: `NOT_APPLICABLE` means the rule does not apply
 * to this document type, `NOT_AVAILABLE` means its input was missing. Drawing
 * either as a failure would tell an officer the document fell short of a rule
 * that was never tested against it.
 */
function ValidationRowComponent({ check, defaultExpanded = false }: ValidationRowProps) {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const presentation = VALIDATION_STATUS_PRESENTATION[check.status];

  const tone = {
    PASS: theme.color.positive,
    FAIL: theme.color.critical,
    REVIEW: theme.color.caution,
    NOT_APPLICABLE: theme.color.textTertiary,
    NOT_AVAILABLE: theme.color.textTertiary,
  }[check.status];

  const muted = check.status === 'NOT_APPLICABLE' || check.status === 'NOT_AVAILABLE';

  return (
    <View>
      <Pressable
        onPress={() => setExpanded((current) => !current)}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        accessibilityLabel={`${check.rule_id}. ${presentation.a11yLabel}`}
        accessibilityHint={expanded ? 'Collapses the rule detail' : 'Expands the rule detail'}
        style={({ pressed }) => [
          styles.header,
          {
            paddingVertical: theme.spacing.md,
            paddingHorizontal: theme.spacing.lg,
            minHeight: theme.controlHeight.minTouchTarget,
            backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
          },
        ]}
      >
        <Text role="mono" weight="bold" style={[styles.glyph, { color: tone }]} accessible={false}>
          {presentation.glyph}
        </Text>

        <View style={styles.headerText}>
          <Text
            role="body"
            weight="medium"
            tone={muted ? 'tertiary' : 'primary'}
            accessible={false}
          >
            {humanise(check.rule_id)}
          </Text>
          <Text
            role="caption"
            tone="tertiary"
            numberOfLines={expanded ? undefined : 1}
            accessible={false}
          >
            {check.message}
          </Text>
        </View>

        <Text role="caption" tone="tertiary" accessible={false}>
          {expanded ? '−' : '+'}
        </Text>
      </Pressable>

      {expanded ? (
        <Animated.View
          entering={FadeIn.duration(theme.duration.fast)}
          style={{
            paddingHorizontal: theme.spacing.lg,
            paddingBottom: theme.spacing.lg,
            paddingLeft: theme.spacing.lg + 24,
          }}
        >
          <DetailBlock label="Status" value={presentation.label} valueColour={tone} />
          <DetailBlock label="Result" value={check.message} />
          {check.observed ? <DetailBlock label="Observed" value={check.observed} mono /> : null}
          {check.expectation ? (
            <DetailBlock label="Rule requires" value={check.expectation} />
          ) : null}
          {check.fields && check.fields.length > 0 ? (
            <DetailBlock label="Fields read" value={check.fields.join(', ')} />
          ) : null}
          <DetailBlock label="Rule identifier" value={check.rule_id} mono />
        </Animated.View>
      ) : null}
    </View>
  );
}

/** `mrz_checksum` reads as `MRZ checksum` for an officer. */
function humanise(ruleId: string): string {
  const words = ruleId.replace(/_/g, ' ').trim();
  const capitalised = words.charAt(0).toUpperCase() + words.slice(1);
  return capitalised.replace(/\bmrz\b/gi, 'MRZ').replace(/\bdob\b/gi, 'date of birth');
}

function DetailBlock({
  label,
  value,
  mono = false,
  valueColour,
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueColour?: string;
}) {
  const theme = useTheme();
  return (
    <View style={{ marginTop: theme.spacing.md }}>
      <Text role="label" tone="tertiary">
        {label}
      </Text>
      <Text
        role={mono ? 'monoSmall' : 'caption'}
        tone="secondary"
        style={[{ marginTop: theme.spacing.xxs }, valueColour ? { color: valueColour } : null]}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  glyph: { width: 12, textAlign: 'center' },
  headerText: { flex: 1, minWidth: 0 },
});

export const ValidationRow = memo(ValidationRowComponent);
