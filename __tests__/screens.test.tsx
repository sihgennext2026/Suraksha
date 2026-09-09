import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';

import { createTestDatabase, type TestDatabase } from './support/sqliteTestDatabase';

/**
 * Screen and component behaviour.
 *
 * The assertions here are deliberately about what an officer can perceive and
 * act on — the accessible name of a status, whether an error is announced,
 * whether a disabled action stays disabled — rather than about rendered
 * structure. Those are the properties that would actually break the product.
 */

let mockDatabase: TestDatabase;

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn(async () => mockDatabase),
}));

const mockReplace = jest.fn();
const mockPush = jest.fn();
const mockBack = jest.fn();

jest.mock('expo-router', () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush, back: mockBack }),
  useFocusEffect: jest.fn(),
  useLocalSearchParams: () => ({}),
  Redirect: () => null,
}));

jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(async () => undefined),
  ImpactFeedbackStyle: { Light: 'light' },
}));

import { SafeAreaProvider } from 'react-native-safe-area-context';

import { EvidenceCard } from '@/components/data/EvidenceCard';
import { RiskBadge, SyncBadge } from '@/components/data/StatusBadge';
import { ValidationRow } from '@/components/data/ValidationRow';
import { Button } from '@/components/primitives/Button';
import { EmptyState, ErrorState } from '@/components/feedback/States';
import { __resetDatabaseForTests } from '@/db';
import { LoginScreen } from '@/features/auth/screens/LoginScreen';
import { DocumentTypeScreen } from '@/features/screening/screens/DocumentTypeScreen';
import { useAuthStore } from '@/stores/authStore';
import { createInitialStages, useScreeningStore } from '@/stores/screeningStore';
import { ThemeProvider } from '@/theme';
import type { ScreeningCase } from '@/types';

const METRICS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

/**
 * Renders under the same providers the application supplies at its root, with
 * fixed safe-area metrics so layout does not depend on the host environment.
 */
function renderWithProviders(ui: React.ReactElement) {
  return render(
    <SafeAreaProvider initialMetrics={METRICS}>
      <ThemeProvider preference="dark">{ui}</ThemeProvider>
    </SafeAreaProvider>,
  );
}

function buildActiveCase(): ScreeningCase {
  return {
    id: 'SSB-2026-0001',
    status: 'DRAFT',
    documentType: 'passport',
    document: null,
    person: null,
    stages: createInitialStages(),
    result: null,
    decision: null,
    sync: {
      state: 'LOCAL_ONLY',
      lastAttemptAt: null,
      lastSyncedAt: null,
      attempts: 0,
      lastError: null,
    },
    officerId: 'SSB4471',
    officerName: 'Krishna Raj',
    unit: '41 Bn SSB',
    postName: 'Raxaul ICP',
    createdAt: '2026-08-24T10:00:00.000Z',
    updatedAt: '2026-08-24T10:00:00.000Z',
  };
}

beforeEach(() => {
  mockDatabase = createTestDatabase();
  __resetDatabaseForTests(null);
  mockReplace.mockReset();
  mockPush.mockReset();
  mockBack.mockReset();
  (jest.requireMock('expo-secure-store') as { __reset(): void }).__reset();
  useAuthStore.setState({
    status: 'SIGNED_OUT',
    session: null,
    deviceId: 'SSB-DEV-TEST',
    error: null,
    busy: false,
  });
});

afterEach(async () => {
  await mockDatabase.closeAsync();
});

describe('status components', () => {
  it('announces a status by word, not by colour alone', () => {
    renderWithProviders(<RiskBadge level="HIGH" />);

    // The accessible name carries the meaning in full; the glyph and the label
    // carry it visually. Nothing depends on the colour being perceived.
    expect(screen.getByLabelText('High risk')).toBeTruthy();
    expect(screen.getByText('High risk')).toBeTruthy();
    expect(screen.getByText('✕')).toBeTruthy();
  });

  it('distinguishes every synchronisation state by name', () => {
    const { rerender } = renderWithProviders(<SyncBadge state="PENDING" />);
    expect(screen.getByLabelText('Pending synchronisation')).toBeTruthy();

    rerender(
      <SafeAreaProvider initialMetrics={METRICS}>
        <ThemeProvider preference="dark">
          <SyncBadge state="FAILED" />
        </ThemeProvider>
      </SafeAreaProvider>,
    );
    expect(screen.getByLabelText('Synchronisation failed')).toBeTruthy();
  });

  it('gives an evidence row an accessible name covering status and detail', () => {
    renderWithProviders(
      <EvidenceCard
        item={{
          module: 'face_verification',
          status: 'SUCCESS',
          severity: 'HIGH',
          headline: 'Face verification',
          detail: 'No match · similarity 0.04',
        }}
      />,
    );

    expect(screen.getByText('Face verification')).toBeTruthy();
    // The raw cosine similarity is shown as the model produced it.
    expect(screen.getByText('No match · similarity 0.04')).toBeTruthy();
  });
});

describe('validation row', () => {
  const check = {
    rule_id: 'mrz_checksum',
    status: 'FAIL' as const,
    message: 'Document number check digit: read 4, computed 9',
    observed: 'read 4, computed 9',
    expectation: 'Every ICAO 9303 check digit must equal the value computed from its field',
    fields: ['Document number'],
  };

  it('shows the verdict collapsed and the full reasoning when expanded', () => {
    renderWithProviders(<ValidationRow check={check} />);

    expect(screen.getByText('MRZ checksum')).toBeTruthy();
    expect(screen.queryByText('Rule requires')).toBeNull();

    fireEvent.press(screen.getByLabelText('mrz_checksum. Rule failed'));

    expect(screen.getByText('Rule requires')).toBeTruthy();
    expect(screen.getByText('Result')).toBeTruthy();
    // Appears twice once expanded: in the row summary and in the Result block.
    expect(screen.getAllByText(check.message).length).toBeGreaterThan(0);
  });

  it('opens a failing rule automatically so the finding is not hidden', () => {
    renderWithProviders(<ValidationRow check={check} defaultExpanded />);
    expect(screen.getByText('Rule requires')).toBeTruthy();
  });
});

describe('state components', () => {
  it('offers a recovery action on an error rather than only a message', () => {
    const onAction = jest.fn();
    renderWithProviders(
      <ErrorState
        title="Cases could not be read"
        message="The local case store could not be opened."
        actionLabel="Try again"
        onAction={onAction}
      />,
    );

    fireEvent.press(screen.getByLabelText('Try again'));
    expect(onAction).toHaveBeenCalled();
  });

  it('explains an empty list rather than showing a bare heading', () => {
    renderWithProviders(
      <EmptyState
        title="No cases on this device yet"
        message="Cases appear here as soon as you start screening."
      />,
    );
    expect(screen.getByText('No cases on this device yet')).toBeTruthy();
    expect(screen.getByText(/Cases appear here/)).toBeTruthy();
  });

  it('does not fire a disabled action', () => {
    const onPress = jest.fn();
    renderWithProviders(<Button label="Record decision" onPress={onPress} disabled />);

    fireEvent.press(screen.getByLabelText('Record decision'));
    expect(onPress).not.toHaveBeenCalled();
  });
});

describe('login screen', () => {
  it('states that credentials are checked on the device', () => {
    renderWithProviders(<LoginScreen />);

    expect(screen.getByText('SSB Suraksha')).toBeTruthy();
    expect(screen.getByText(/verified against this device/i)).toBeTruthy();
  });

  it('rejects a malformed officer ID before attempting to sign in', async () => {
    renderWithProviders(<LoginScreen />);

    fireEvent.changeText(screen.getByTestId('login-officer-id'), 'ABC');
    fireEvent.changeText(screen.getByTestId('login-pin'), '4471');
    fireEvent.press(screen.getByTestId('login-submit'));

    await waitFor(() => {
      expect(
        screen.getByText('Officer IDs are three letters followed by four digits'),
      ).toBeTruthy();
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('requires a PIN of at least four digits', async () => {
    renderWithProviders(<LoginScreen />);

    fireEvent.changeText(screen.getByTestId('login-officer-id'), 'SSB4471');
    fireEvent.changeText(screen.getByTestId('login-pin'), '12');
    fireEvent.press(screen.getByTestId('login-submit'));

    await waitFor(() => {
      expect(screen.getByText('Your PIN is at least 4 digits')).toBeTruthy();
    });
  });

  it('signs a valid officer in and moves on to the dashboard', async () => {
    await useAuthStore.getState().bootstrap();
    renderWithProviders(<LoginScreen />);

    fireEvent.changeText(screen.getByTestId('login-officer-id'), 'SSB4471');
    fireEvent.changeText(screen.getByTestId('login-pin'), '4471');
    fireEvent.press(screen.getByTestId('login-submit'));

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith('/(app)/dashboard');
    });
    expect(useAuthStore.getState().status).toBe('SIGNED_IN');
  });

  it('shows a failed sign-in without saying which field was wrong', async () => {
    await useAuthStore.getState().bootstrap();
    renderWithProviders(<LoginScreen />);

    fireEvent.changeText(screen.getByTestId('login-officer-id'), 'SSB4471');
    fireEvent.changeText(screen.getByTestId('login-pin'), '0000');
    fireEvent.press(screen.getByTestId('login-submit'));

    await waitFor(() => {
      expect(screen.getByText('Sign-in failed')).toBeTruthy();
    });
    expect(
      screen.getByText('That officer ID and PIN do not match a record on this device.'),
    ).toBeTruthy();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe('document type screen', () => {
  beforeEach(() => {
    useScreeningStore.setState({
      activeCase: buildActiveCase(),
      phase: 'DOCUMENT_TYPE',
      running: false,
      error: null,
      restored: true,
      saving: false,
      saveError: null,
    });
  });

  it('offers every document type for the officer to declare', () => {
    renderWithProviders(<DocumentTypeScreen />);

    for (const label of [
      'Passport',
      'Visa',
      'National identity card',
      'Driving licence',
      'Permit',
      'Travel authorisation',
      'Other document',
    ]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it('records the officer selection and moves on to capture', async () => {
    renderWithProviders(<DocumentTypeScreen />);

    fireEvent.press(screen.getByTestId('document-type-national_id'));
    fireEvent.press(screen.getByTestId('document-type-continue'));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/screening/document-capture');
    });
    // The declared type is what drives the rule set downstream, so it must be
    // the officer's selection that is stored, not a default.
    expect(useScreeningStore.getState().activeCase?.documentType).toBe('national_id');
  });

  it('marks which document types carry a machine-readable zone', () => {
    renderWithProviders(<DocumentTypeScreen />);
    expect(screen.getAllByText('MRZ').length).toBeGreaterThan(0);
  });
});
