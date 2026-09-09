import React from 'react';
import { View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { MODULE_LABELS } from '@/constants/screening';
import { useTheme } from '@/theme';
import type { Envelope, ModuleName } from '@/contracts';

interface ModuleUnavailableProps {
  module: ModuleName;
  /** Null when the screening has not run at all. */
  envelope: Envelope<unknown> | null;
}

/**
 * What an officer sees when a check did not produce a result.
 *
 * The wording is the whole point. A module that failed or was never implemented
 * has told us nothing — not that the document is sound, and not that it is
 * suspect. This screen says that in as many words, because a blank or apologetic
 * screen reads as reassurance, and reassurance is exactly what an absent check
 * cannot offer.
 */
export function ModuleUnavailable({ module, envelope }: ModuleUnavailableProps) {
  const theme = useTheme();
  const label = MODULE_LABELS[module];

  const status = envelope?.status ?? 'NOT_AVAILABLE';
  const reason = envelope?.errors[0]?.message;
  const heading = status === 'FAILED' ? 'This check could not run' : 'This check was not available';

  return (
    <>
      <Panel style={{ marginTop: theme.spacing.lg }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Text role="title" weight="bold" tone="tertiary" accessible={false}>
            –
          </Text>
          <Text
            role="title"
            tone="secondary"
            accessibilityRole="header"
            accessibilityLabel={`${label}. ${heading}.`}
          >
            {heading.toUpperCase()}
          </Text>
        </View>

        <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
          {reason ?? `${label} did not produce a result for this screening.`}
        </Text>
      </Panel>

      <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
        <Text role="label" tone="tertiary">
          What this means
        </Text>
        <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
          Nothing was measured, so there is no finding here either way. The risk assessment
          excluded this check rather than counting it as a pass or a failure. Weigh the
          document on the checks that did run, and on your own examination.
        </Text>
      </Panel>

      <Section title="Details">
        <Panel padded={false}>
          <KeyValueRow label="Check" value={label} />
          <KeyValueRow label="Status" value={status} mono />
          {envelope ? <KeyValueRow label="Reason" value={envelope.errors[0]?.code ?? '—'} mono /> : null}
          {envelope ? <KeyValueRow label="Service" value={envelope.model_version} mono /> : null}
        </Panel>
      </Section>
    </>
  );
}
