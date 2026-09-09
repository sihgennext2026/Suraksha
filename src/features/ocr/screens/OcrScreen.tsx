import React from 'react';
import { useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Screen } from '@/components/layout/Screen';
import { ModuleUnavailable } from '@/features/screening/components/ModuleUnavailable';
import { useScreeningGuard } from '@/features/screening/useScreeningGuard';
import { hasEvidence } from '@/contracts';

import { OcrDetails } from '../components/OcrDetails';

/** Extracted document information for the screening in progress. */
export function OcrScreen() {
  const router = useRouter();
  const activeCase = useScreeningGuard('CASE');
  const envelope = activeCase?.result?.ocr ?? null;

  if (!activeCase) return null;

  return (
    <>
      <AppHeader
        title="Document information"
        subtitle={activeCase.id}
        onBack={() => router.back()}
        backLabel="Back to the screening result"
      />
      <Screen>
        {envelope && hasEvidence(envelope) ? (
          <OcrDetails envelope={envelope} result={envelope.result} />
        ) : (
          <ModuleUnavailable module="ocr" envelope={envelope} />
        )}
      </Screen>
    </>
  );
}
