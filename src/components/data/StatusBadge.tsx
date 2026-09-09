import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { Text } from '@/components/primitives/Text';
import {
  CASE_STATUS_PRESENTATION,
  DECISION_PRESENTATION,
  FACE_DECISION_PRESENTATION,
  MODULE_STATUS_PRESENTATION,
  RISK_LEVEL_PRESENTATION,
  SEVERITY_PRESENTATION,
  SYNC_STATE_PRESENTATION,
  VALIDATION_DECISION_PRESENTATION,
  type StatusPresentation,
} from '@/constants/labels';
import { useTheme } from '@/theme';
import type {
  FaceDecision,
  ModuleStatus,
  RiskLevel,
  Severity,
  ValidationDecision,
} from '@/contracts';
import type { CaseStatus, OfficerDecisionType, SyncState } from '@/types/case';

/** The five semantic channels a badge can occupy. */
export type BadgeTone = 'positive' | 'caution' | 'critical' | 'info' | 'neutral';

interface BadgeProps {
  presentation: StatusPresentation;
  tone: BadgeTone;
  size?: 'small' | 'medium';
  emphasis?: 'subtle' | 'solid';
  style?: StyleProp<ViewStyle>;
}

/**
 * Status chip.
 *
 * The glyph is not decoration: it is the second, colour-independent carrier of
 * the status, alongside the text label. That is what makes every status in this
 * application readable in greyscale, in direct sunlight, and to an officer with
 * a colour vision deficiency.
 */
export function StatusBadge({
  presentation,
  tone,
  size = 'medium',
  emphasis = 'subtle',
  style,
}: BadgeProps) {
  const theme = useTheme();

  const palette = {
    positive: {
      fg: theme.color.positive,
      bg: theme.color.positiveSubtle,
      border: theme.color.positiveBorder,
    },
    caution: {
      fg: theme.color.caution,
      bg: theme.color.cautionSubtle,
      border: theme.color.cautionBorder,
    },
    critical: {
      fg: theme.color.critical,
      bg: theme.color.criticalSubtle,
      border: theme.color.criticalBorder,
    },
    info: { fg: theme.color.info, bg: theme.color.infoSubtle, border: theme.color.infoBorder },
    neutral: {
      fg: theme.color.neutral,
      bg: theme.color.neutralSubtle,
      border: theme.color.neutralBorder,
    },
  }[tone];

  const solid = emphasis === 'solid';
  const foreground = solid ? theme.color.textOnAccent : palette.fg;

  return (
    <View
      accessible
      accessibilityRole="text"
      accessibilityLabel={presentation.a11yLabel}
      style={[
        styles.badge,
        {
          backgroundColor: solid ? palette.fg : palette.bg,
          borderColor: solid ? palette.fg : palette.border,
          borderWidth: theme.borderWidth.thin,
          borderRadius: theme.radii.sm,
          paddingHorizontal: size === 'small' ? theme.spacing.xs : theme.spacing.sm,
          paddingVertical: size === 'small' ? 1 : 3,
          gap: size === 'small' ? 3 : 5,
        },
        style,
      ]}
    >
      <Text role="monoSmall" weight="bold" style={{ color: foreground }} accessible={false}>
        {presentation.glyph}
      </Text>
      <Text
        role="caption"
        weight="semibold"
        style={{ color: foreground, fontSize: size === 'small' ? 10 : 12 }}
        numberOfLines={1}
        accessible={false}
      >
        {presentation.label}
      </Text>
    </View>
  );
}

/**
 * Module status.
 *
 * `FAILED` and `NOT_AVAILABLE` are deliberately neutral rather than critical:
 * a module that did not run is an absence of evidence, and colouring it red
 * would read as a finding against the document.
 */
const MODULE_STATUS_TONE: Record<ModuleStatus, BadgeTone> = {
  SUCCESS: 'positive',
  PARTIAL: 'caution',
  FAILED: 'neutral',
  NOT_AVAILABLE: 'neutral',
};

export function ModuleStatusBadge({
  status,
  size,
}: {
  status: ModuleStatus;
  size?: 'small' | 'medium';
}) {
  return (
    <StatusBadge
      presentation={MODULE_STATUS_PRESENTATION[status]}
      tone={MODULE_STATUS_TONE[status]}
      size={size}
    />
  );
}

const SEVERITY_TONE: Record<Severity, BadgeTone> = {
  NONE: 'positive',
  LOW: 'info',
  MEDIUM: 'caution',
  HIGH: 'critical',
};

export function SeverityBadge({
  severity,
  size,
}: {
  severity: Severity;
  size?: 'small' | 'medium';
}) {
  return (
    <StatusBadge
      presentation={SEVERITY_PRESENTATION[severity]}
      tone={SEVERITY_TONE[severity]}
      size={size}
    />
  );
}

const RISK_TONE: Record<RiskLevel, BadgeTone> = {
  LOW: 'positive',
  REVIEW: 'caution',
  HIGH: 'critical',
};

export function RiskBadge({
  level,
  size,
  emphasis = 'subtle',
}: {
  level: RiskLevel;
  size?: 'small' | 'medium';
  emphasis?: 'subtle' | 'solid';
}) {
  return (
    <StatusBadge
      presentation={RISK_LEVEL_PRESENTATION[level]}
      tone={RISK_TONE[level]}
      size={size}
      emphasis={emphasis}
    />
  );
}

const FACE_TONE: Record<FaceDecision, BadgeTone> = {
  MATCH: 'positive',
  REVIEW: 'caution',
  NO_MATCH: 'critical',
};

export function FaceDecisionBadge({
  decision,
  size,
}: {
  decision: FaceDecision;
  size?: 'small' | 'medium';
}) {
  return (
    <StatusBadge
      presentation={FACE_DECISION_PRESENTATION[decision]}
      tone={FACE_TONE[decision]}
      size={size}
    />
  );
}

const VALIDATION_TONE: Record<ValidationDecision, BadgeTone> = {
  VALID: 'positive',
  REVIEW: 'caution',
  INVALID: 'critical',
};

export function ValidationDecisionBadge({
  decision,
  size,
}: {
  decision: ValidationDecision;
  size?: 'small' | 'medium';
}) {
  return (
    <StatusBadge
      presentation={VALIDATION_DECISION_PRESENTATION[decision]}
      tone={VALIDATION_TONE[decision]}
      size={size}
    />
  );
}

const SYNC_TONE: Record<SyncState, BadgeTone> = {
  LOCAL_ONLY: 'neutral',
  PENDING: 'caution',
  SYNCING: 'info',
  SYNCED: 'positive',
  FAILED: 'critical',
};

export function SyncBadge({ state, size }: { state: SyncState; size?: 'small' | 'medium' }) {
  return (
    <StatusBadge
      presentation={SYNC_STATE_PRESENTATION[state]}
      tone={SYNC_TONE[state]}
      size={size}
    />
  );
}

const CASE_STATUS_TONE: Record<CaseStatus, BadgeTone> = {
  DRAFT: 'neutral',
  CAPTURING: 'info',
  SCREENING: 'info',
  AWAITING_DECISION: 'caution',
  COMPLETED: 'positive',
  ABANDONED: 'neutral',
};

export function CaseStatusBadge({
  status,
  size,
}: {
  status: CaseStatus;
  size?: 'small' | 'medium';
}) {
  return (
    <StatusBadge
      presentation={CASE_STATUS_PRESENTATION[status]}
      tone={CASE_STATUS_TONE[status]}
      size={size}
    />
  );
}

const DECISION_TONE: Record<OfficerDecisionType, BadgeTone> = {
  CLEAR: 'positive',
  HOLD: 'caution',
  ESCALATE: 'critical',
};

export function DecisionBadge({
  decision,
  size,
  emphasis,
}: {
  decision: OfficerDecisionType;
  size?: 'small' | 'medium';
  emphasis?: 'subtle' | 'solid';
}) {
  return (
    <StatusBadge
      presentation={DECISION_PRESENTATION[decision]}
      tone={DECISION_TONE[decision]}
      size={size}
      emphasis={emphasis}
    />
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
  },
});
