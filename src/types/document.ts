import type { DocumentType } from '@/contracts';

/**
 * Capture-side types.
 *
 * These describe what the device produced, not what a model concluded — the
 * analysis of a capture is a service result and lives in `@/contracts`.
 */

export interface DocumentTypeDescriptor {
  type: DocumentType;
  label: string;
  /** One line describing when to pick this type. */
  hint: string;
  /** Whether this document carries a machine-readable zone. */
  hasMrz: boolean;
  /** Capture guide aspect ratio (width / height). */
  captureAspectRatio: number;
  /**
   * Whether the backend can extract and validate this type at all. Officers can
   * still select an unsupported type — refusing the selection would push them
   * into declaring the wrong one — but the screening will report those modules
   * as NOT_AVAILABLE rather than borrowing another type's rules.
   */
  backendSupported: boolean;
}

export type CaptureSource = 'CAMERA' | 'IMPORTED';

/** A captured image held on device. `uri` is a local `file://` path. */
export interface CapturedImage {
  uri: string;
  width: number;
  height: number;
  /** Bytes on disk. Used for the storage budget shown on the dashboard. */
  sizeBytes: number;
  source: CaptureSource;
  capturedAt: string;
}

/**
 * Live capture guidance shown while framing. Produced on-device by the capture
 * UI; it is not a model result and never reaches the case record.
 */
export type CaptureQualityLevel = 'GOOD' | 'ACCEPTABLE' | 'INSUFFICIENT';

export interface DocumentRecord {
  id: string;
  caseId: string;
  /** The type the officer declared. Nothing infers it. */
  declaredType: DocumentType;
  image: CapturedImage;
}

export interface PersonCaptureRecord {
  id: string;
  caseId: string;
  image: CapturedImage;
}
