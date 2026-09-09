import React, { type ReactNode } from 'react';
import { Modal as RNModal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeIn, FadeOut, SlideInDown, SlideOutDown } from 'react-native-reanimated';

import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';

interface SheetProps {
  visible: boolean;
  onDismiss: () => void;
  title: string;
  /** One line under the title explaining what this sheet is for. */
  description?: string;
  children: ReactNode;
  /** Actions pinned to the bottom of the sheet. */
  footer?: ReactNode;
  /** Prevents dismissal by tapping the scrim. Use for destructive confirms. */
  dismissible?: boolean;
  testID?: string;
}

/**
 * A bottom sheet.
 *
 * Used for filters, analysis details, and confirmations — anything that is a
 * detour from the current screen rather than a step forward in the workflow.
 * Workflow steps get their own route so the back gesture behaves predictably.
 */
export function BottomSheet({
  visible,
  onDismiss,
  title,
  description,
  children,
  footer,
  dismissible = true,
  testID,
}: SheetProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { isTablet, contentMaxWidth } = useResponsive();

  return (
    <RNModal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={dismissible ? onDismiss : undefined}
      statusBarTranslucent
    >
      <View style={styles.root} testID={testID}>
        <Animated.View
          entering={FadeIn.duration(theme.duration.fast)}
          exiting={FadeOut.duration(theme.duration.fast)}
          style={StyleSheet.absoluteFill}
        >
          <Pressable
            style={[StyleSheet.absoluteFill, { backgroundColor: theme.color.scrim }]}
            onPress={dismissible ? onDismiss : undefined}
            accessibilityRole="button"
            accessibilityLabel={dismissible ? 'Dismiss' : 'Dialog background'}
            disabled={!dismissible}
          />
        </Animated.View>

        <Animated.View
          entering={SlideInDown.duration(theme.duration.normal)}
          exiting={SlideOutDown.duration(theme.duration.fast)}
          style={[
            styles.sheet,
            {
              backgroundColor: theme.color.surface,
              borderTopLeftRadius: theme.radii.xl,
              borderTopRightRadius: theme.radii.xl,
              borderColor: theme.color.border,
              borderWidth: theme.borderWidth.thin,
              paddingBottom: insets.bottom + theme.spacing.lg,
              maxHeight: '88%',
            },
            isTablet ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : null,
          ]}
        >
          <View style={[styles.grabber, { backgroundColor: theme.color.borderStrong }]} />

          <View style={{ paddingHorizontal: theme.spacing.lg, paddingBottom: theme.spacing.md }}>
            <Text role="subtitle" accessibilityRole="header">
              {title}
            </Text>
            {description ? (
              <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xxs }}>
                {description}
              </Text>
            ) : null}
          </View>

          <ScrollView
            style={styles.body}
            contentContainerStyle={{ paddingHorizontal: theme.spacing.lg }}
            showsVerticalScrollIndicator={false}
          >
            {children}
          </ScrollView>

          {footer ? (
            <View
              style={{
                paddingHorizontal: theme.spacing.lg,
                paddingTop: theme.spacing.md,
                borderTopWidth: theme.borderWidth.thin,
                borderTopColor: theme.color.border,
              }}
            >
              {footer}
            </View>
          ) : null}
        </Animated.View>
      </View>
    </RNModal>
  );
}

interface ConfirmDialogProps {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  testID?: string;
}

/**
 * A blocking confirmation.
 *
 * Reserved for actions that cannot be undone from the officer's side: recording
 * a decision, abandoning a case in progress, clearing local data.
 */
export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel,
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
  testID,
}: ConfirmDialogProps) {
  const theme = useTheme();

  return (
    <RNModal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={[styles.dialogRoot, { backgroundColor: theme.color.scrim }]} testID={testID}>
        <View
          style={[
            styles.dialog,
            {
              backgroundColor: theme.color.surface,
              borderRadius: theme.radii.xl,
              borderColor: theme.color.border,
              borderWidth: theme.borderWidth.thin,
              padding: theme.spacing.xl,
            },
          ]}
        >
          <Text role="subtitle" accessibilityRole="header">
            {title}
          </Text>
          <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.sm }}>
            {message}
          </Text>

          <View style={[styles.dialogActions, { marginTop: theme.spacing.xl }]}>
            <Button label={cancelLabel} onPress={onCancel} variant="secondary" size="medium" />
            <Button
              label={confirmLabel}
              onPress={onConfirm}
              variant={destructive ? 'danger' : 'primary'}
              size="medium"
              haptic
            />
          </View>
        </View>
      </View>
    </RNModal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  sheet: { width: '100%' },
  grabber: {
    width: 36,
    height: 4,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 8,
    marginBottom: 12,
  },
  body: { flexGrow: 0 },
  dialogRoot: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  dialog: { width: '100%', maxWidth: 400 },
  dialogActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
});
