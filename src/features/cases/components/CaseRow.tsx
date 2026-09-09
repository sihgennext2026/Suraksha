import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { CaseStatusBadge, RiskBadge, SyncBadge } from '@/components/data/StatusBadge';
import { documentTypeLabel } from '@/constants/documents';
import { useTheme } from '@/theme';
import type { CaseSummary } from '@/types';
import { formatRelative } from '@/utils/date';

interface CaseRowProps {
  summary: CaseSummary;
  onPress: (id: string) => void;
  /** Draws the separator above the row. Omitted on the first row of a group. */
  separated?: boolean;
}

/**
 * One case in the list.
 *
 * The reference is set in monospace and given the most prominent position,
 * because that is what an officer is matching against a paper record or a radio
 * call. Risk and sync state sit on the second line: important, but only after
 * the officer has found the right case.
 */
function CaseRowComponent({ summary, onPress, separated = true }: CaseRowProps) {
  const theme = useTheme();

  const accessibilityLabel = [
    `Case ${summary.id}`,
    documentTypeLabel(summary.documentType),
    summary.riskLevel ? `${summary.riskLevel.toLowerCase()} risk` : 'not yet screened',
    summary.maskedDocumentNumber
      ? `document ending ${summary.maskedDocumentNumber.slice(-4)}`
      : null,
    formatRelative(summary.createdAt),
  ]
    .filter(Boolean)
    .join(', ');

  return (
    <Pressable
      onPress={() => onPress(summary.id)}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      accessibilityHint="Opens the full case record"
      style={({ pressed }) => [
        {
          paddingVertical: theme.spacing.md,
          paddingHorizontal: theme.spacing.lg,
          minHeight: theme.controlHeight.minTouchTarget,
          borderTopWidth: separated ? theme.borderWidth.thin : 0,
          borderTopColor: theme.color.border,
          backgroundColor: pressed ? theme.color.surfaceSunken : 'transparent',
        },
      ]}
    >
      <View style={styles.topRow}>
        <Text role="mono" weight="semibold" accessible={false}>
          {summary.id}
        </Text>
        <Text role="caption" tone="tertiary" accessible={false}>
          {formatRelative(summary.createdAt)}
        </Text>
      </View>

      <View style={[styles.metaRow, { marginTop: theme.spacing.xxs }]}>
        <Text role="caption" tone="secondary" numberOfLines={1} accessible={false}>
          {documentTypeLabel(summary.documentType)}
          {summary.maskedDocumentNumber ? ` · ${summary.maskedDocumentNumber}` : ''}
        </Text>
      </View>

      <View style={[styles.badgeRow, { marginTop: theme.spacing.sm }]}>
        {summary.riskLevel ? (
          <RiskBadge level={summary.riskLevel} size="small" />
        ) : (
          <CaseStatusBadge status={summary.status} size="small" />
        )}
        {summary.riskLevel && summary.status !== 'COMPLETED' ? (
          <CaseStatusBadge status={summary.status} size="small" />
        ) : null}
        <SyncBadge state={summary.syncState} size="small" />
        {summary.riskScore !== null ? (
          <Text role="monoSmall" tone="tertiary" style={styles.score} accessible={false}>
            {Math.round(summary.riskScore)}/100
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  topRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  metaRow: { flexDirection: 'row', alignItems: 'center' },
  badgeRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
  score: { marginLeft: 'auto' },
});

export const CaseRow = memo(CaseRowComponent);
