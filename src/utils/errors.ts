import { ScreeningServiceError, type ServiceFailure } from '@/types';

const GENERIC_MESSAGE = 'Something went wrong. Please try again.';

/**
 * Turns anything thrown into a failure that is safe to render. Officers must
 * never see a stack trace or an internal code — they see a sentence and, where
 * one exists, an action they can take.
 */
export function toServiceFailure(error: unknown): ServiceFailure {
  if (error instanceof ScreeningServiceError) {
    return { code: error.code, message: error.message, retryable: error.retryable };
  }
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return { code: 'ABORTED', message: 'The operation was cancelled.', retryable: true };
    }
    return { code: 'UNEXPECTED', message: GENERIC_MESSAGE, retryable: true };
  }
  return { code: 'UNKNOWN', message: GENERIC_MESSAGE, retryable: true };
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

export function failure(code: string, message: string, retryable = true): ScreeningServiceError {
  return new ScreeningServiceError({ code, message, retryable });
}
