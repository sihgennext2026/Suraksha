import React, { useCallback, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, type FlashMode } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import {
  CaptureControls,
  CaptureFrame,
  CaptureStatus,
  CaptureToggle,
} from '@/components/overlay/CaptureOverlay';
import { EmptyState, ErrorState } from '@/components/feedback/States';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { ROUTES } from '@/constants/routes';
import { useScreeningStore } from '@/stores/screeningStore';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useTheme } from '@/theme';
import type { CapturedImage } from '@/types';
import { nowIso } from '@/utils/date';
import { createLogger } from '@/utils/logger';

import { useLiveCaptureFeedback } from '../useLiveCaptureFeedback';

const log = createLogger('document-capture');

/**
 * Step 2 — document capture.
 *
 * The camera fills the screen and the chrome sits over it, because the officer's
 * attention belongs on the document, not on the application. The status panel
 * always names both the problem and the correction, and capture is never
 * silently blocked: an officer who judges the frame acceptable can capture
 * anyway and decide on the review screen.
 */
export interface DocumentCaptureScreenProps {
  /**
   * Which face of the document is being photographed.
   *
   * The camera, the overlay and the live guidance are identical for both, so
   * the screen is parameterised rather than copied: a second implementation
   * would drift, and the officer would meet two subtly different cameras in one
   * workflow.
   */
  side?: 'front' | 'back';
}

export function DocumentCaptureScreen({ side = 'front' }: DocumentCaptureScreenProps = {}) {
  const router = useRouter();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const activeCase = useScreeningGuard('CASE');

  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [flash, setFlash] = useState<FlashMode>('off');
  const [torch, setTorch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const attachDocument = useScreeningStore((state) => state.attachDocument);
  const attachDocumentBack = useScreeningStore((state) => state.attachDocumentBack);
  const isBack = side === 'back';
  const feedback = useLiveCaptureFeedback('DOCUMENT', cameraReady && !busy);

  const descriptor = activeCase
    ? DOCUMENT_TYPE_DESCRIPTORS[activeCase.documentType]
    : DOCUMENT_TYPE_DESCRIPTORS.passport;

  const attachAndReview = useCallback(
    async (image: CapturedImage) => {
      if (!activeCase) return;
      // No inference happens here. The capture is stored, and every model result
      // arrives later from a single screening call - which is what stops the app
      // holding a second, divergent view of what the document is.
      if (isBack) {
        await attachDocumentBack(image);
        // Back to the review, where both sides are now shown together.
        router.back();
        return;
      }
      await attachDocument(image);
      router.push(ROUTES.screening.documentReview);
    },
    [activeCase, attachDocument, attachDocumentBack, isBack, router],
  );

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current || busy) return;
    setBusy(true);
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.9,
        skipProcessing: false,
      });
      if (!photo) throw new Error('No photo returned');
      await attachAndReview({
        uri: photo.uri,
        width: photo.width,
        height: photo.height,
        sizeBytes: 0,
        source: 'CAMERA',
        capturedAt: nowIso(),
      });
    } catch (caught) {
      log.error('Document capture failed');
      void caught;
      setError('The document could not be captured. Try again, or import an image instead.');
    } finally {
      setBusy(false);
    }
  }, [busy, attachAndReview]);

  const handleImport = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 0.9,
        allowsEditing: false,
      });
      if (result.canceled || !result.assets[0]) return;
      const asset = result.assets[0];
      await attachAndReview({
        uri: asset.uri,
        width: asset.width,
        height: asset.height,
        sizeBytes: asset.fileSize ?? 0,
        source: 'IMPORTED',
        capturedAt: nowIso(),
      });
    } catch (caught) {
      log.error('Document import failed');
      void caught;
      setError('That image could not be imported. Choose a different one, or use the camera.');
    } finally {
      setBusy(false);
    }
  }, [attachAndReview]);

  if (!activeCase) return null;

  if (!permission) {
    return <View style={[styles.root, { backgroundColor: theme.color.surfaceInverse }]} />;
  }

  if (!permission.granted) {
    return (
      <View style={[styles.root, { backgroundColor: theme.color.canvas, paddingTop: insets.top }]}>
        <EmptyState
          glyph="◉"
          title="Camera access is needed"
          message="Document capture uses the camera. You can grant access now, or import a document image that is already on this device."
          actionLabel={permission.canAskAgain ? 'Grant camera access' : 'Import an image instead'}
          onAction={permission.canAskAgain ? () => void requestPermission() : handleImport}
          secondaryActionLabel="Back"
          onSecondaryAction={() => router.back()}
        />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: theme.color.surfaceInverse }]}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
        flash={flash}
        enableTorch={torch}
        animateShutter={false}
        onCameraReady={() => setCameraReady(true)}
      />

      <CaptureFrame aspectRatio={descriptor.captureAspectRatio} tone={feedback.tone} />

      <View style={[styles.chrome, { paddingTop: insets.top + theme.spacing.md }]}>
        <View style={styles.topBar}>
          <Button
            label="Back"
            onPress={() => router.back()}
            variant="ghost"
            size="medium"
            style={styles.backButton}
          />
          <View style={styles.topMeta}>
            <Text role="monoSmall" style={{ color: '#C8D3DE' }}>
              {activeCase.id}
            </Text>
            <Text role="label" style={{ color: '#FFFFFF' }}>
              {isBack ? `${descriptor.label} · reverse` : descriptor.label}
            </Text>
          </View>
          <View style={styles.backButton} />
        </View>

        <View style={styles.spacer} />

        <View style={[styles.bottom, { paddingBottom: insets.bottom + theme.spacing.lg }]}>
          {error ? (
            <View style={{ marginBottom: theme.spacing.md }}>
              <ErrorState title="Capture failed" message={error} />
            </View>
          ) : (
            <CaptureStatus
              tone={feedback.tone}
              headline={feedback.headline}
              instruction={feedback.instruction}
              checks={feedback.checks}
            />
          )}

          <View style={{ marginTop: theme.spacing.xl }}>
            <CaptureControls
              onCapture={handleCapture}
              busy={busy}
              captureLabel="Capture document"
              leftControl={
                <CaptureToggle
                  label={flash === 'off' ? 'OFF' : 'ON'}
                  glyph="⚡"
                  active={flash !== 'off'}
                  onPress={() => {
                    const next: FlashMode = flash === 'off' ? 'on' : 'off';
                    setFlash(next);
                    setTorch(next === 'on');
                  }}
                  accessibilityLabel={flash === 'off' ? 'Turn the light on' : 'Turn the light off'}
                />
              }
              rightControl={
                <CaptureToggle
                  label="FILE"
                  glyph="⤓"
                  onPress={handleImport}
                  accessibilityLabel="Import a document image from this device"
                />
              }
            />
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  chrome: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    paddingHorizontal: 16,
  },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  topMeta: { alignItems: 'center' },
  backButton: { width: 72 },
  spacer: { flex: 1 },
  bottom: {},
});
