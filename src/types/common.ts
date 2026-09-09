/**
 * Application-level primitives.
 *
 * Anything a *service* produces lives in `@/contracts` instead. This file holds
 * only concepts the application itself owns.
 */

/** ISO-8601 timestamp, always UTC, e.g. `2026-08-24T09:41:07.412Z`. */
export type IsoDateTime = string;

/** ISO-8601 calendar date, e.g. `2003-05-12`. */
export type IsoDate = string;

/** Identifier of a persisted screening case, e.g. `SSB-2026-0842`. */
export type CaseId = string;

/**
 * A failure that reached the UI.
 *
 * Service failures arrive inside a contract envelope's `errors`; this type is
 * for faults raised on the device — storage, camera, navigation.
 */
export interface ServiceFailure {
  /** Stable machine code for logs and retry logic. Never shown to officers. */
  code: string;
  /** Plain-language sentence safe to display verbatim. */
  message: string;
  /** Whether retrying the same input could reasonably succeed. */
  retryable: boolean;
}

export class ScreeningServiceError extends Error implements ServiceFailure {
  readonly code: string;
  readonly retryable: boolean;

  constructor(failure: ServiceFailure) {
    super(failure.message);
    this.name = 'ScreeningServiceError';
    this.code = failure.code;
    this.retryable = failure.retryable;
  }
}
