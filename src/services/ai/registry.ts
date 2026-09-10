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
import { resolveScreeningServiceUrl } from '@/config/screeningService';

import { HttpScreeningService } from './httpScreeningService';

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
   *
   * This only ever selects a replayed fixture. It cannot alter what the real
   * service returns, and it is ignored whenever one is configured.
   */
  scenario?: string;
  /** Officer override for the service address; falls back to the build's. */
  serviceUrl?: string | null;
}

/**
 * Chooses the implementation for this device.
 *
 * A configured service address means real inference, and the fixtures are then
 * unreachable: replaying an invented result against a capture the officer just
 * took would be indistinguishable, to them, from a real finding. With no
 * address configured there is nothing to call, so the app falls back to
 * replaying generated documents and says so in Settings.
 */
export function getScreeningService(options: ServiceRegistryOptions = {}): ScreeningService {
  const baseUrl = resolveScreeningServiceUrl(options.serviceUrl);
  if (baseUrl) return new HttpScreeningService({ baseUrl });
  return new MockScreeningService(options.scenario);
}

/** Whether this device is wired to a real screening service. */
export function isUsingRealScreening(serviceUrl?: string | null): boolean {
  return resolveScreeningServiceUrl(serviceUrl) !== null;
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

/**
 * What each module is backed by for this device, right now.
 *
 * Three of these change with the service address, and the read-out has to
 * change with them: an officer looking at findings needs to know whether a
 * model produced them or a fixture did, and a table that always claimed one or
 * the other would be worse than no table.
 */
export function getIntegrationStatus(serviceUrl?: string | null): readonly ModuleIntegration[] {
  const live = isUsingRealScreening(serviceUrl);

  const wired = (
    module: string,
    implementation: string,
    liveNote: string,
  ): ModuleIntegration => ({
    module,
    state: live ? 'ACTIVE' : 'MOCK',
    implementation: live ? implementation : `${implementation} — not reachable`,
    note: live
      ? liveNote
      : 'No screening service is configured, so the app replays a generated document. Nothing here came from this capture.',
  });

  return [
    wired(
      'Field extraction (OCR/MRZ)',
      'Phase_1: PP-LCNet orientation, U-Net detection, PP-OCRv5',
      'The capture is detected, rectified and read by the extraction pipeline.',
    ),
    wired(
      'Rule validation',
      'backend/validation deterministic rule sets',
      'Rules run against the fields extraction actually read from this document.',
    ),
    wired(
      'Face verification',
      'SCRFD detection + ArcFace R50 (buffalo_m)',
      'Cosine similarity of the document portrait against the subject capture. Thresholds are the pipeline’s own calibrated values and remain provisional.',
    ),
    ...STATIC_INTEGRATION_STATUS,
  ];
}

const STATIC_INTEGRATION_STATUS: readonly ModuleIntegration[] = [
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
