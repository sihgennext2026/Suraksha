import React, { useCallback } from 'react';
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useCameraPermissions } from 'expo-camera';
import { useQuery } from '@tanstack/react-query';

import { AppHeader } from '@/components/layout/AppHeader';
import { Panel, Section } from '@/components/layout/Panel';
import { Screen } from '@/components/layout/Screen';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { InlineNotice, LoadingState } from '@/components/feedback/States';
import { ROLE_LABEL } from '@/constants/labels';
import { LATEST_SCHEMA_VERSION } from '@/db/migrations';
import { SystemStatusPanel } from '@/features/dashboard/components/SystemStatusPanel';
import { useSystemStatus } from '@/features/dashboard/useSystemStatus';
import { INTEGRATION_STATUS } from '@/services/ai/registry';
import { authService } from '@/services/api/authService';
import { useAuthStore } from '@/stores/authStore';
import { useTheme } from '@/theme';

/**
 * Device setup and diagnostics.
 *
 * Reachable before sign-in, because the things that stop a screening — camera
 * permission, full storage, a database that will not open — all need fixing
 * before an officer is standing at the counter, not after.
 */
export function DeviceSetupScreen() {
  const router = useRouter();
  const theme = useTheme();
  const deviceId = useAuthStore((state) => state.deviceId);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const status = useSystemStatus();

  const officers = useQuery({
    queryKey: ['enrolled-officers'],
    queryFn: () => authService.enrolledOfficers(),
  });

  const handleRequestCamera = useCallback(async () => {
    await requestCameraPermission();
    status.refetch();
  }, [requestCameraPermission, status]);

  return (
    <>
      <AppHeader
        title="Device setup"
        subtitle="Readiness and enrolment"
        onBack={() => router.back()}
        backLabel="Back to sign-in"
      />
      <Screen onRefresh={status.refetch} refreshing={status.isLoading}>
        {cameraPermission && !cameraPermission.granted ? (
          <InlineNotice
            tone="caution"
            title="Camera permission is not granted"
            message="Document and subject capture cannot run without it. Screening of an already imported image will still work."
            actionLabel={cameraPermission.canAskAgain ? 'Grant camera access' : 'Open settings'}
            onAction={handleRequestCamera}
          />
        ) : null}

        <Section title="Subsystems">
          <SystemStatusPanel subsystems={status.subsystems} />
        </Section>

        <Section title="Device" description="Recorded against every case created on this device.">
          <Panel padded={false}>
            <KeyValueRow label="Device identifier" value={deviceId ?? 'Not enrolled'} mono />
            <KeyValueRow label="Database schema" value={`Version ${LATEST_SCHEMA_VERSION}`} mono />
            <KeyValueRow label="Application" value="1.0.0 (prototype)" mono />
          </Panel>
        </Section>

        <Section
          title="Screening modules"
          description="What each check is backed by on this device today."
        >
          <Panel padded={false}>
            {INTEGRATION_STATUS.map((entry, index) => (
              <View
                key={entry.module}
                accessible
                accessibilityRole="text"
                accessibilityLabel={`${entry.module}. ${entry.state.replace(/_/g, ' ').toLowerCase()}. ${entry.note}`}
                style={{
                  padding: theme.spacing.lg,
                  borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                  borderTopColor: theme.color.border,
                }}
              >
                <View style={styles.officerRow}>
                  <Text role="body" weight="medium" style={styles.officerText} accessible={false}>
                    {entry.module}
                  </Text>
                  <Text
                    role="monoSmall"
                    weight="bold"
                    style={{
                      color:
                        entry.state === 'ACTIVE'
                          ? theme.color.positive
                          : entry.state === 'MOCK'
                            ? theme.color.caution
                            : theme.color.textTertiary,
                    }}
                    accessible={false}
                  >
                    {entry.state}
                  </Text>
                </View>
                <Text role="caption" tone="tertiary" style={{ marginTop: 2 }} accessible={false}>
                  {entry.implementation}
                </Text>
                <Text
                  role="caption"
                  tone="secondary"
                  style={{ marginTop: theme.spacing.xs }}
                  accessible={false}
                >
                  {entry.note}
                </Text>
              </View>
            ))}
          </Panel>
        </Section>

        <Section
          title="Enrolled officers"
          description="Officers who can sign in on this device without connectivity."
        >
          {officers.isLoading ? (
            <LoadingState label="Reading enrolment records" fill={false} />
          ) : (
            <Panel padded={false}>
              {(officers.data ?? []).map((officer, index) => (
                <View
                  key={officer.id}
                  style={[
                    styles.officerRow,
                    {
                      padding: theme.spacing.lg,
                      borderTopWidth: index === 0 ? 0 : theme.borderWidth.thin,
                      borderTopColor: theme.color.border,
                    },
                  ]}
                >
                  <View style={styles.officerText}>
                    <Text role="body" weight="medium">
                      {officer.rank} {officer.name}
                    </Text>
                    <Text role="caption" tone="tertiary">
                      {officer.unit} · {officer.postName}
                    </Text>
                  </View>
                  <Text role="monoSmall" tone="secondary">
                    {ROLE_LABEL[officer.role]}
                  </Text>
                </View>
              ))}
            </Panel>
          )}
        </Section>

        <Section title="Data handling">
          <Panel tone="sunken">
            <Text role="caption" tone="secondary">
              Captured imagery and extracted data are held in the application container on this
              device and are transmitted only to the central case service, once, when connectivity
              allows. Nothing is sent during screening itself.
            </Text>
            <Text role="caption" tone="tertiary" style={{ marginTop: theme.spacing.sm }}>
              This is a prototype build. Container encryption, key management and the retention
              schedule are marked for implementation before any operational deployment.
            </Text>
          </Panel>
        </Section>

        <Button
          label="Back to sign-in"
          onPress={() => router.back()}
          variant="secondary"
          fullWidth
          style={{ marginTop: theme.spacing.xxl }}
        />
      </Screen>
    </>
  );
}

const styles = StyleSheet.create({
  officerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  officerText: { flex: 1, minWidth: 0 },
});
