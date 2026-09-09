import React from 'react';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Screen } from '@/components/layout/Screen';
import { ModuleUnavailable } from '@/features/screening/components/ModuleUnavailable';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { hasEvidence } from '@/contracts';

import { ForensicsDetails } from '../components/ForensicsDetails';

/** Tamper detection for the screening in progress. */
export function ForensicsScreen() {
  const router = useRouter();
  const activeCase = useScreeningGuard('CASE');
  const envelope = activeCase?.result?.document_forensics ?? null;
  const documentUri = activeCase?.document?.image.uri;

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Document forensics"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />
      <Screen>
        {envelope && hasEvidence(envelope) && documentUri ? (
          <ForensicsDetails
            envelope={envelope}
            result={envelope.result}
            documentImageUri={documentUri}
            documentType={activeCase.documentType}
          />
        ) : (
          <ModuleUnavailable module="document_forensics" envelope={envelope} />
        )}
      </Screen>
    </>
  );
}
