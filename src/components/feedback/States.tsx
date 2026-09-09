import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { Panel } from '@/components/layout/Panel';
import { useTheme } from '@/theme';

interface BaseStateProps {
  title: string;
  /** One or two sentences. Says what happened and what to do about it. */
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  testID?: string;
}

/**
 * The four screen states, built on one layout.
 *
 * Every list and every asynchronous screen resolves to one of these rather than
 * rendering nothing. Error text is written for the officer: it says what could
 * not be done and what to try, never a code.
 */
function StateLayout({
  glyph,
  glyphTone,
  title,
  message,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  testID,
}: BaseStateProps & { glyph: string; glyphTone: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.container, { padding: theme.spacing.xxxl }]} testID={testID}>
      <View
        style={[
          styles.glyphRing,
          {
            borderColor: theme.color.border,
            borderWidth: theme.borderWidth.thin,
            borderRadius: theme.radii.pill,
            marginBottom: theme.spacing.lg,
          },
        ]}
      >
        <Text role="title" style={{ color: glyphTone }} accessible={false}>
          {glyph}
        </Text>
      </View>

      <Text role="subtitle" align="center" accessibilityRole="header">
        {title}
      </Text>
      {message ? (
        <Text
          role="body"
          tone="secondary"
          align="center"
          style={{ marginTop: theme.spacing.sm, maxWidth: 380 }}
        >
          {message}
        </Text>
      ) : null}

      {onAction && actionLabel ? (
        <View style={{ marginTop: theme.spacing.xl }}>
          <Button label={actionLabel} onPress={onAction} variant="primary" size="medium" />
        </View>
      ) : null}
      {onSecondaryAction && secondaryActionLabel ? (
        <View style={{ marginTop: theme.spacing.sm }}>
          <Button
            label={secondaryActionLabel}
            onPress={onSecondaryAction}
            variant="ghost"
            size="medium"
          />
        </View>
      ) : null}
    </View>
  );
}

export function EmptyState(props: BaseStateProps & { glyph?: string }) {
  const theme = useTheme();
  const { glyph = '□', ...rest } = props;
  return <StateLayout {...rest} glyph={glyph} glyphTone={theme.color.textTertiary} />;
}

export function ErrorState(props: BaseStateProps) {
  const theme = useTheme();
  return <StateLayout {...props} glyph="!" glyphTone={theme.color.critical} />;
}

export function OfflineState(props: BaseStateProps) {
  const theme = useTheme();
  return <StateLayout {...props} glyph="⚡" glyphTone={theme.color.caution} />;
}

interface LoadingStateProps {
  /** What is being loaded, e.g. `Loading cases`. */
  label?: string;
  /** Fills the available space rather than sitting inline. */
  fill?: boolean;
  testID?: string;
}

export function LoadingState({ label = 'Loading', fill = true, testID }: LoadingStateProps) {
  const theme = useTheme();
  return (
    <View
      style={[fill ? styles.container : styles.inline, { padding: theme.spacing.xxxl }]}
      accessibilityRole="progressbar"
      accessibilityLabel={label}
      testID={testID}
    >
      <ActivityIndicator size="small" color={theme.color.textSecondary} />
      <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.md }}>
        {label}
      </Text>
    </View>
  );
}

interface InlineNoticeProps {
  tone: 'info' | 'caution' | 'critical' | 'positive';
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

/** A banner inside a screen. Used for offline notices and recoverable errors. */
export function InlineNotice({ tone, title, message, actionLabel, onAction }: InlineNoticeProps) {
  const theme = useTheme();
  const glyph = { info: 'i', caution: '!', critical: '✕', positive: '✓' }[tone];
  const panelTone = {
    info: 'accent',
    caution: 'caution',
    critical: 'critical',
    positive: 'positive',
  } as const;
  const textTone = {
    info: 'info',
    caution: 'caution',
    critical: 'critical',
    positive: 'positive',
  } as const;

  return (
    <Panel tone={panelTone[tone]} style={{ marginTop: theme.spacing.md }}>
      <View style={styles.noticeRow}>
        <Text role="body" weight="bold" tone={textTone[tone]} accessible={false}>
          {glyph}
        </Text>
        <View style={styles.noticeBody}>
          <Text role="body" weight="semibold">
            {title}
          </Text>
          {message ? (
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xxs }}>
              {message}
            </Text>
          ) : null}
          {onAction && actionLabel ? (
            <View style={{ marginTop: theme.spacing.md, alignSelf: 'flex-start' }}>
              <Button label={actionLabel} onPress={onAction} variant="secondary" size="medium" />
            </View>
          ) : null}
        </View>
      </View>
    </Panel>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  inline: { alignItems: 'center', justifyContent: 'center' },
  glyphRing: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
  noticeRow: { flexDirection: 'row', gap: 10 },
  noticeBody: { flex: 1, minWidth: 0 },
});
