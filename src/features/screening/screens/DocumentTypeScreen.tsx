import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { ConfirmDialog } from '@/components/overlay/Sheet';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { ROUTES } from '@/constants/routes';
import { useScreeningStore } from '@/stores/screeningStore';
import { useTheme } from '@/theme';
import { DOCUMENT_TYPES, type DocumentType } from '@/types';

import { useScreeningGuard } from '../useScreeningGuard';

/**
 * Step 1 — document type.
 *
 * The officer declares the type; nothing infers it. That is a deliberate design
 * rule rather than a limitation: the declared type selects the rule set, the
 * expected machine-readable zone, and the reference distribution the anomaly
 * detector measures against. A model that silently mis-classified a document
 * would change all three without anyone noticing.
 */
export function DocumentTypeScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('CASE');

  const setDocumentType = useScreeningStore((state) => state.setDocumentType);
  const abandon = useScreeningStore((state) => state.abandon);

  const [selected, setSelected] = useState<DocumentType>(activeCase?.documentType ?? 'passport');
  const [confirmExit, setConfirmExit] = useState(false);

  const handleContinue = useCallback(async () => {
    await setDocumentType(selected);
    router.push(ROUTES.screening.documentCapture);
  }, [setDocumentType, selected, router]);

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Document type"
        eyebrow="Step 1 of 5"
        subtitle={activeCase.id}
        onBack={() => setConfirmExit(true)}
        backLabel="Leave this screening"
      />

      <Screen
        footer={
          <Button
            label="Continue to capture"
            onPress={handleContinue}
            fullWidth
            testID="document-type-continue"
          />
        }
      >
        <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
          Select the document the subject has presented. Your selection determines which validation
          rules apply and which reference set the document is measured against, so it is not
          inferred automatically.
        </Text>

        <Section title="Document presented">
          <Panel padded={false}>
            {DOCUMENT_TYPES.map((type, index) => {
              const descriptor = DOCUMENT_TYPE_DESCRIPTORS[type];
              const isSelected = selected === type;
              return (
                <Pressable
                  key={type}
                  onPress={() => setSelected(type)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: isSelected }}
                  accessibilityLabel={`${descriptor.label}. ${descriptor.hint}`}
                  testID={`document-type-${type}`}
                  style={({ pressed }) => [
                    styles.option,
                    {
                      padding: theme.spacing.lg,
                      minHeight: theme.controlHeight.minTouchTarget,
                      borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                      borderTopColor: theme.color.border,
                      backgroundColor: isSelected
                        ? theme.color.accentSubtle
                        : pressed
                          ? theme.color.surfaceSunken
                          : 'transparent',
                    },
                  ]}
                >
                  <View
                    style={[
                      styles.radio,
                      {
                        borderRadius: theme.radii.pill,
                        borderWidth: isSelected ? 6 : theme.borderWidth.medium,
                        borderColor: isSelected ? theme.color.accent : theme.color.borderStrong,
                      },
                    ]}
                  />
                  <View style={styles.optionText}>
                    <Text
                      role="body"
                      weight={isSelected ? 'semibold' : 'regular'}
                      accessible={false}
                    >
                      {descriptor.label}
                    </Text>
                    <Text role="caption" tone="tertiary" accessible={false}>
                      {descriptor.hint}
                    </Text>
                  </View>
                  {descriptor.hasMrz ? (
                    <Text role="monoSmall" tone="tertiary" accessible={false}>
                      MRZ
                    </Text>
                  ) : null}
                </Pressable>
              );
            })}
          </Panel>
        </Section>

        <Section title="What happens next">
          <Panel tone="sunken">
            <Step index={1} text="Capture the document with the on-screen guide." />
            <Step index={2} text="Review the capture and confirm it is legible." />
            <Step index={3} text="Capture the subject's face." />
            <Step index={4} text="Run the screening — eight stages, all on this device." />
            <Step index={5} text="Review the evidence and record your decision." />
          </Panel>
        </Section>
      </Screen>

      <ConfirmDialog
        visible={confirmExit}
        title="Leave this screening?"
        message={`Case ${activeCase.id} will be marked abandoned. Nothing has been captured yet, so nothing is lost.`}
        confirmLabel="Leave"
        destructive
        onConfirm={async () => {
          setConfirmExit(false);
          await abandon();
          router.replace(ROUTES.app.dashboard);
        }}
        onCancel={() => setConfirmExit(false)}
      />
    </>
  );
}

function Step({ index, text }: { index: number; text: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.step, index > 1 && { marginTop: theme.spacing.md }]}>
      <Text role="monoSmall" tone="tertiary" style={styles.stepIndex} accessible={false}>
        {index}
      </Text>
      <Text role="caption" tone="secondary" style={styles.stepText}>
        {text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  option: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  radio: { width: 18, height: 18 },
  optionText: { flex: 1, minWidth: 0 },
  step: { flexDirection: 'row', gap: 10 },
  stepIndex: { width: 12 },
  stepText: { flex: 1 },
});
