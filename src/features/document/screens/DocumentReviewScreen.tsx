import React, { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { ZoomableImage } from '@/components/data/ZoomableImage';
import { InlineNotice } from '@/components/feedback/States';
import { DOCUMENT_TYPE_DESCRIPTORS, UNSUPPORTED_TYPE_NOTICE } from '@/constants/documents';
import { ROUTES } from '@/constants/routes';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useTheme } from '@/theme';

/**
 * Step 3 — document review.
 *
 * The last point at which a poor capture costs seconds rather than a full
 * re-screening. Detection confidence and per-axis quality are shown so the
 * decision to proceed is informed: an officer who can see that sharpness is the
 * weak axis knows to steady the device rather than change the lighting.
 */
export function DocumentReviewScreen() {
  const router = useRouter();
  const theme = useTheme();
  const activeCase = useScreeningGuard('DOCUMENT');
  const [confirming, setConfirming] = useState(false);

  const handleConfirm = useCallback(() => {
    setConfirming(true);
    router.push(ROUTES.screening.personCapture);
    setConfirming(false);
  }, [router]);

  if (!activeCase?.document) return null;

  const { document } = activeCase;
  const descriptor = DOCUMENT_TYPE_DESCRIPTORS[document.declaredType];
  const expectsBack = descriptor.hasBackFields;

  return (
    <>
      <AppHeader
        title="Review capture"
        eyebrow="Step 3 of 5"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to document capture"
      />

      <Screen
        footer={
          <View style={styles.footer}>
            <Button
              label="Retake"
              onPress={() => router.back()}
              variant="secondary"
              style={styles.footerButton}
            />
            <Button
              label="Confirm document"
              onPress={handleConfirm}
              loading={confirming}
              style={styles.footerAction}
              testID="document-review-confirm"
            />
          </View>
        }
      >
        <View style={{ marginTop: theme.spacing.lg }}>
          <ZoomableImage
            uri={document.image.uri}
            aspectRatio={descriptor.captureAspectRatio}
            accessibilityLabel={`Captured ${descriptor.label.toLowerCase()}, pinch to zoom`}
          />
        </View>

        {/*
          The officer's own eye is the check at this point. No model has run yet -
          detection, extraction and tamper analysis all happen in one screening
          call after the subject photograph is taken - so this screen asks the
          only question it can honestly ask: is this legible?
        */}
        {/*
          The reverse is offered here rather than forced into the sequence. Some
          types carry nothing on the back that this pipeline reads, and an
          officer at a counter may not get a second shot — so a missing reverse
          resolves to REVIEW downstream, never to a failure.
        */}
        <Section
          title="Reverse side"
          description={
            expectsBack
              ? `The reverse of a ${descriptor.label.toLowerCase()} carries fields the front does not.`
              : 'Optional for this document type.'
          }
        >
          {document.backImage ? (
            <>
              <ZoomableImage
                uri={document.backImage.uri}
                aspectRatio={descriptor.captureAspectRatio}
                accessibilityLabel={`Captured reverse of the ${descriptor.label.toLowerCase()}, pinch to zoom`}
              />
              <Button
                label="Retake reverse"
                onPress={() => router.push(ROUTES.screening.documentBackCapture)}
                variant="secondary"
                style={{ marginTop: theme.spacing.md }}
              />
            </>
          ) : (
            <>
              <Button
                label="Capture reverse"
                onPress={() => router.push(ROUTES.screening.documentBackCapture)}
                variant="secondary"
                fullWidth
                testID="document-review-capture-back"
              />
              {expectsBack ? (
                <InlineNotice
                  tone="info"
                  title="Some fields are printed only on the reverse"
                  message="Without it those fields are reported as needing confirmation rather than read. The screening still runs."
                />
              ) : null}
            </>
          )}
        </Section>

        <Panel tone="sunken" style={{ marginTop: theme.spacing.lg }}>
          <Text role="label" tone="tertiary">
            Before you confirm
          </Text>
          <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
            Check that the whole document is in frame, that it is in focus, and that no
            glare obscures the photograph, the data fields or the machine-readable zone.
            Retaking now costs seconds; a poor capture weakens every finding that follows.
          </Text>
        </Panel>

        {!descriptor.backendSupported ? (
          <InlineNotice
            tone="caution"
            title={`${descriptor.label} is not supported by extraction`}
            message={UNSUPPORTED_TYPE_NOTICE}
          />
        ) : null}

        <Section title="Capture">
          <Panel padded={false}>
            <KeyValueRow label="Document type" value={descriptor.label} />
            <KeyValueRow
              label="Source"
              value={document.image.source === 'CAMERA' ? 'Device camera' : 'Imported image'}
            />
            <KeyValueRow
              label="Resolution"
              value={`${document.image.width} × ${document.image.height}`}
              mono
            />
            <KeyValueRow
              label="Machine-readable zone"
              value={descriptor.hasMrz ? 'Expected on this document' : 'Not carried by this type'}
            />
          </Panel>
        </Section>
      </Screen>
    </>
  );
}

const styles = StyleSheet.create({
  footer: { flexDirection: 'row', gap: 8 },
  footerButton: { flexShrink: 0 },
  footerAction: { flex: 1 },
});
