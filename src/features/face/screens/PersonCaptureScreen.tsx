import React, { useCallback, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { CameraView, useCameraPermissions, type CameraType } from 'expo-camera';
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
import { ROUTES } from '@/constants/routes';
import { useLiveCaptureFeedback } from '@/features/document/useLiveCaptureFeedback';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { useScreeningStore } from '@/stores/screeningStore';
import { useSettingsStore } from '@/stores/settingsStore';
import { useTheme } from '@/theme';
import { nowIso } from '@/utils/date';
import { createLogger } from '@/utils/logger';

const log = createLogger('person-capture');

/**
 * Step 4 — subject capture.
 *
 * Deliberately not a liveness check. This is a controlled capture performed by
 * an officer with the subject in front of them, so the physical presence of the
 * person is already established; the photograph exists solely as one half of the
 * 1:1 comparison against the document portrait.
 *
 * The three failure states the officer actually meets — no face, more than one
 * face, and poor quality — each name their own correction.
 */
export function PersonCaptureScreen() {
  const router = useRouter();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const activeCase = useScreeningGuard('DOCUMENT');

  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [facing, setFacing] = useState<CameraType>('back');
  const [cameraReady, setCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const attachPerson = useScreeningStore((state) => state.attachPerson);
  const runScreening = useScreeningStore((state) => state.runScreening);
  const scenario = useSettingsStore((state) => state.forcedScenario);
  const feedback = useLiveCaptureFeedback('FACE', cameraReady && !busy);

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current || busy || !activeCase) return;
    setBusy(true);
    setError(null);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.9 });
      if (!photo) throw new Error('No photo returned');

      // The capture is stored as-is. Whether it contains a usable face is a
      // question for the face verification service, which reports NO_FACE as a
      // FAILED module rather than as a non-match - the app does not pre-judge it.
      await attachPerson({
        uri: photo.uri,
        width: photo.width,
        height: photo.height,
        sizeBytes: 0,
        source: 'CAMERA' as const,
        capturedAt: nowIso(),
      });
      // The run is started here, by the officer's action, rather than by an
      // effect on the progress screen: the progress screen stays a pure view of
      // a run that is already under way.
      void runScreening({ scenario: scenario ?? undefined });
      router.push(ROUTES.screening.progress);
    } catch (caught) {
      log.error('Person capture failed');
      void caught;
      setError('The photograph could not be captured. Try again.');
    } finally {
      setBusy(false);
    }
  }, [busy, activeCase, attachPerson, runScreening, scenario, router]);

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
          message="The subject photograph is one half of the face comparison, so it has to be taken now, with the camera."
          actionLabel={permission.canAskAgain ? 'Grant camera access' : 'Back'}
          onAction={permission.canAskAgain ? () => void requestPermission() : () => router.back()}
        />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: theme.color.surfaceInverse }]}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing={facing}
        animateShutter={false}
        onCameraReady={() => setCameraReady(true)}
      />

      <CaptureFrame aspectRatio={0.78} widthFraction={0.66} tone={feedback.tone} shape="oval" />

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
              Subject photograph
            </Text>
          </View>
          <View style={styles.backButton} />
        </View>

        <View style={styles.spacer} />

        <View style={[styles.bottom, { paddingBottom: insets.bottom + theme.spacing.lg }]}>
          {error ? (
            <View style={{ marginBottom: theme.spacing.md }}>
              <ErrorState
                title="Capture not accepted"
                message={error}
                actionLabel="Try again"
                onAction={() => setError(null)}
              />
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
              captureLabel="Capture subject photograph"
              leftControl={
                <CaptureToggle
                  label="FLIP"
                  glyph="⇄"
                  onPress={() => setFacing((current) => (current === 'back' ? 'front' : 'back'))}
                  accessibilityLabel="Switch between the front and rear camera"
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
