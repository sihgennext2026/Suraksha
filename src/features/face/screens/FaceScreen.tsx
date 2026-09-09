import React from 'react';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Screen } from '@/components/layout/Screen';
import { ModuleUnavailable } from '@/features/screening/components/ModuleUnavailable';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { hasEvidence } from '@/contracts';

import { FaceDetails } from '../components/FaceDetails';

/** Face verification for the screening in progress. */
export function FaceScreen() {
  const router = useRouter();
  const activeCase = useScreeningGuard('CASE');
  const envelope = activeCase?.result?.face_verification ?? null;

  const documentUri = activeCase?.document?.image.uri;
  const personUri = activeCase?.person?.image.uri;

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Face verification"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />
      <Screen>
        {envelope && hasEvidence(envelope) && documentUri && personUri ? (
          <FaceDetails
            envelope={envelope}
            result={envelope.result}
            documentImageUri={documentUri}
            personImageUri={personUri}
          />
        ) : (
          <ModuleUnavailable module="face_verification" envelope={envelope} />
        )}
      </Screen>
    </>
  );
}
