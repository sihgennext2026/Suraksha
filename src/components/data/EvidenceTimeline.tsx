import React, { memo } from 'react';
import { StyleSheet, View } from 'react-native';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';
import type { AuditEvent, AuditEventType } from '@/types';
import { formatDateTime, formatTimeWithSeconds } from '@/utils/date';

interface EvidenceTimelineProps {
  events: readonly AuditEvent[];
  /** Shows the full date on each row rather than just the time. */
  showDates?: boolean;
}

/**
 * The audit trail for a case.
 *
 * Rendered as a strict chronological list with seconds, because the value of an
 * audit trail is the sequence: what the officer saw, in what order, and when
 * they acted on it. Events are never reordered or grouped.
 */
const DECISION_EVENTS: ReadonlySet<AuditEventType> = new Set([
  'OFFICER_DECISION',
  'CASE_SAVED',
  'SCREENING_FAILED',
  'SYNC_FAILED',
]);

function EvidenceTimelineComponent({ events, showDates = false }: EvidenceTimelineProps) {
  const theme = useTheme();

  return (
    <View>
      {events.map((event, index) => {
        const isLast = index === events.length - 1;
        const emphasised = DECISION_EVENTS.has(event.type);
        const adverse = event.type === 'SCREENING_FAILED' || event.type === 'SYNC_FAILED';

        const markerColour = adverse
          ? theme.color.critical
          : emphasised
            ? theme.color.accent
            : theme.color.borderStrong;

        return (
          <View
            key={event.id}
            style={styles.row}
            accessible
            accessibilityRole="text"
            accessibilityLabel={`${formatDateTime(event.occurredAt)}. ${event.description}. Recorded by ${event.actorName}`}
          >
            <View style={styles.gutter}>
              <View
                style={{
                  width: emphasised ? 9 : 7,
                  height: emphasised ? 9 : 7,
                  borderRadius: theme.radii.pill,
                  backgroundColor: markerColour,
                  marginTop: 5,
                }}
              />
              {!isLast ? (
                <View
                  style={[
                    styles.connector,
                    { backgroundColor: theme.color.border, width: theme.borderWidth.thin },
                  ]}
                />
              ) : null}
            </View>

            <View style={[styles.body, { paddingBottom: isLast ? 0 : theme.spacing.lg }]}>
              <Text
                role="body"
                weight={emphasised ? 'semibold' : 'regular'}
                tone={adverse ? 'critical' : 'primary'}
                accessible={false}
              >
                {event.description}
              </Text>
              <Text role="monoSmall" tone="tertiary" style={{ marginTop: 2 }} accessible={false}>
                {showDates
                  ? formatDateTime(event.occurredAt)
                  : formatTimeWithSeconds(event.occurredAt)}
                {'  ·  '}
                {event.actorName}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12 },
  gutter: { alignItems: 'center', width: 10 },
  connector: { flex: 1, marginVertical: 3 },
  body: { flex: 1, minWidth: 0 },
});

export const EvidenceTimeline = memo(EvidenceTimelineComponent);
