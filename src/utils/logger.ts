/**
 * Diagnostic logging with redaction built in.
 *
 * Screening handles names, document numbers, dates of birth and biometric
 * imagery. None of it may reach a log sink. Callers pass structured context and
 * this module drops any key that is known to carry personal data, plus anything
 * that looks like a file URI (which would identify a stored capture).
 *
 * TODO(production): route `emit` to the on-device secure audit sink rather than
 * the console, and ship redacted diagnostics only with explicit officer consent.
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export type LogContext = Record<string, string | number | boolean | null | undefined>;

const REDACTED_KEYS = new Set([
  'name',
  'surname',
  'givennames',
  'givenname',
  'documentnumber',
  'passportnumber',
  'dateofbirth',
  'dob',
  'personalnumber',
  'placeofbirth',
  'mrz',
  'mrzline',
  'lines',
  'uri',
  'imageuri',
  'base64',
  'pin',
  'password',
  'token',
  'remarks',
]);

function redact(context: LogContext | undefined): LogContext | undefined {
  if (!context) return undefined;
  const output: LogContext = {};
  for (const [key, value] of Object.entries(context)) {
    if (REDACTED_KEYS.has(key.toLowerCase())) {
      output[key] = '[redacted]';
      continue;
    }
    if (typeof value === 'string' && value.startsWith('file://')) {
      output[key] = '[redacted:uri]';
      continue;
    }
    output[key] = value;
  }
  return output;
}

function emit(level: LogLevel, scope: string, message: string, context?: LogContext): void {
  if (!__DEV__ && level === 'debug') return;
  const payload = redact(context);
  const line = `[${scope}] ${message}`;
  if (level === 'error') {
    console.error(line, payload ?? '');
  } else if (level === 'warn') {
    console.warn(line, payload ?? '');
  } else if (__DEV__) {
    console.log(line, payload ?? '');
  }
}

export interface Logger {
  debug(message: string, context?: LogContext): void;
  info(message: string, context?: LogContext): void;
  warn(message: string, context?: LogContext): void;
  error(message: string, context?: LogContext): void;
}

export function createLogger(scope: string): Logger {
  return {
    debug: (message, context) => emit('debug', scope, message, context),
    info: (message, context) => emit('info', scope, message, context),
    warn: (message, context) => emit('warn', scope, message, context),
    error: (message, context) => emit('error', scope, message, context),
  };
}
