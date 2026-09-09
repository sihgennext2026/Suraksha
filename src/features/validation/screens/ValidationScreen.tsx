import React from 'react';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Screen } from '@/components/layout/Screen';
import { ModuleUnavailable } from '@/features/screening/components/ModuleUnavailable';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { hasEvidence } from '@/contracts';

import { ValidationDetails } from '../components/ValidationDetails';

/** Deterministic rule results for the screening in progress. */
export function ValidationScreen() {
  const router = useRouter();
  const activeCase = useScreeningGuard('CASE');
  const envelope = activeCase?.result?.validation ?? null;

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Rule validation"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />
      <Screen>
        {envelope && hasEvidence(envelope) ? (
          <ValidationDetails envelope={envelope} result={envelope.result} />
        ) : (
          <ModuleUnavailable module="validation" envelope={envelope} />
        )}
      </Screen>
    </>
  );
}
