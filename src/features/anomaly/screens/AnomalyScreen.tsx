import React from 'react';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Screen } from '@/components/layout/Screen';
import { ModuleUnavailable } from '@/features/screening/components/ModuleUnavailable';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';

import { AnomalyDetails } from '../components/AnomalyDetails';

/**
 * Anomaly analysis for the screening in progress.
 *
 * PatchCore is not implemented, so this reliably renders the unavailable state.
 * `AnomalyDetails` handles that case itself rather than delegating to the
 * generic placeholder, because the explanation an officer needs here is
 * specific: nothing was looked for, so nothing was found.
 */
export function AnomalyScreen() {
  const router = useRouter();
  const activeCase = useScreeningGuard('CASE');
  const envelope = activeCase?.result?.anomaly ?? null;
  const documentUri = activeCase?.document?.image.uri;

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Anomaly analysis"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />
      <Screen>
        {envelope ? (
          <AnomalyDetails
            envelope={envelope}
            documentImageUri={documentUri ?? ''}
            documentType={activeCase.documentType}
          />
        ) : (
          <ModuleUnavailable module="anomaly" envelope={null} />
        )}
      </Screen>
    </>
  );
}
