/**
 * Cancellation error.
 *
 * `DOMException` is not guaranteed to exist on every JavaScript runtime React
 * Native ships with, and where it does exist its constructor signature is not
 * consistent. Defining the error here means cancellation is recognised the same
 * way on every platform, which matters because the pipeline distinguishes a
 * cancelled run from a failed one.
 */
export class AbortError extends Error {
  constructor(message = 'The operation was cancelled.') {
    super(message);
    this.name = 'AbortError';
  }
}

/** Awaitable pause. Used by mock services to emulate inference latency. */
export function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new AbortError());
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new AbortError());
    }
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
