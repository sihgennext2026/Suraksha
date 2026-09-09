import type { ScreeningModuleServices, ScreeningService } from './contracts';
import {
  MockDocumentForensicsService,
  MockDocumentVerificationService,
  MockFaceVerificationService,
  MockRiskService,
  MockValidationService,
  UnavailableAnomalyService,
} from '@/services/mock/mockModuleServices';
import { MockScreeningService } from '@/services/mock/mockScreeningService';

/**
 * The single point at which the application binds to an implementation.
 *
 * Everything upstream depends on the interfaces in `contracts.ts`. Nothing in
 * `app/`, `features/`, `stores/` or `db/` names a mock class, so introducing a
 * real backend means editing this file and nothing else.
 *
 * TODO(production): select from build configuration —
 *   HttpScreeningService     when the post has a reachable screening service
 *   OnDeviceScreeningService when the runtimes are installed locally
 *   MockScreeningService     development and demonstration only
 * The offline-first requirement means the mock is not the fallback for a lost
 * connection: a real deployment runs the models on the device, and the network
 * only decides when a finished case is uploaded.
 */

export interface ServiceRegistryOptions {
  /**
   * Forces a specific scenario. Exposed through Settings so every module state
   * — including tamper detection and a failed module — can be exercised on real
   * hardware rather than only in tests.
   */
  scenario?: string;
}

export function getScreeningService(options: ServiceRegistryOptions = {}): ScreeningService {
  return new MockScreeningService(options.scenario);
}

/** For a deployment that calls each module separately. */
export function getScreeningModuleServices(
  options: ServiceRegistryOptions = {},
): ScreeningModuleServices {
  return {
    documentVerification: new MockDocumentVerificationService(options.scenario),
    validation: new MockValidationService(options.scenario),
    faceVerification: new MockFaceVerificationService(options.scenario),
    // The one line that changes when DINOv2 lands.
    documentForensics: new MockDocumentForensicsService(options.scenario),
    anomaly: new UnavailableAnomalyService(),
    risk: new MockRiskService(options.scenario),
  };
}

/**
 * What each module is actually backed by right now. Surfaced in Settings so an
 * officer — and anyone evaluating the system — can see which findings come from
 * a real model and which do not.
 */
export type IntegrationState = 'ACTIVE' | 'MOCK' | 'NOT_AVAILABLE' | 'FUTURE';

export interface ModuleIntegration {
  module: string;
  state: IntegrationState;
  implementation: string;
  note: string;
}

export const INTEGRATION_STATUS: readonly ModuleIntegration[] = [
  {
    module: 'Field extraction (OCR/MRZ)',
    state: 'MOCK',
    implementation: 'Phase_1 PP-OCRv5 + U-Net — service exists, not yet wired to the app',
    note: 'The extraction service is built and adapted to the contract. The app replays generated results until the endpoint is reachable.',
  },
  {
    module: 'Rule validation',
    state: 'MOCK',
    implementation: 'backend/validation — service exists, not yet wired to the app',
    note: 'Deterministic rules are implemented in Python and adapted to the contract.',
  },
  {
    module: 'Face verification',
    state: 'MOCK',
    implementation: 'ArcFace R50 (buffalo_m) — pipeline exists, not yet wired to the app',
    note: 'Thresholds are the pipeline’s own calibrated values and are provisional.',
  },
  {
    module: 'Document forensics',
    state: 'MOCK',
    implementation: 'mock-dinov2-v0',
    note: 'DINOv2 is NOT implemented. No model, no weights, no training data. The mock emits the production contract so the boundary can be swapped without further change.',
  },
  {
    module: 'Anomaly detection',
    state: 'NOT_AVAILABLE',
    implementation: 'PatchCore — not built',
    note: 'No service produces this evidence. Every screening reports it as NOT_AVAILABLE; it is never fabricated and never scored.',
  },
  {
    module: 'Risk fusion',
    state: 'ACTIVE',
    implementation: 'Evidence Fusion Engine (deterministic weighted fusion)',
    note: 'Not LightGBM. Weights are an engineering judgement, not a fit to labelled data.',
  },
  {
    module: 'Officer application',
    state: 'ACTIVE',
    implementation: 'React Native, Expo SDK 54',
    note: 'Consumes the canonical case document. Holds no inference logic and no thresholds of its own.',
  },
];
