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
  /**
   * Whether this type prints fields on its reverse that extraction can read.
   *
   * Decides only whether the officer is prompted for a second capture. What the
   * reverse is expected to carry, and how two sides are reconciled, is the merge
   * policy's business and lives in
   * `contracts/python/ssb_contracts/services/field_merge.py`. A wrong value here
   * costs a prompt, never a finding.
   */
  hasBackFields: boolean;
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
  /**
   * The reverse side, where the officer captured one.
   *
   * Null is an ordinary outcome, not an omission: a passport's reverse carries
   * nothing this pipeline reads, and an officer at a counter may not get a
   * second shot. A screening runs either way.
   */
  backImage: CapturedImage | null;
}

export interface PersonCaptureRecord {
  id: string;
  caseId: string;
  image: CapturedImage;
}
