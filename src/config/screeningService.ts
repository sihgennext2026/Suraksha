import Constants from 'expo-constants';

/**
 * Where the screening service lives.
 *
 * The models run off-device: PP-OCRv5, the U-Net document detector and ArcFace
 * R50 are ONNX and Paddle graphs that need a host runtime, so a screening
 * requires the post's service to be reachable. Everything either side of
 * inference — capture, the case record, the officer's decision, the audit trail
 * and the sync queue — remains local, so a case already screened stays fully
 * usable with no network at all.
 *
 * TODO(production): this address belongs in device management, provisioned per
 * post, not typed in by an officer. Runtime configuration exists here so a
 * demonstration can follow a laptop's address around a network.
 *
 * SECURITY — the build sets `android:usesCleartextTraffic="true"`, without
 * which Android 9 and later refuse an `http://` request before it leaves the
 * device, and a screening fails with no packet ever reaching the service. The
 * service speaks plain HTTP on a post's local network, and Android's network
 * security config can only exempt named hosts, not private address ranges, so
 * an address that changes with the network cannot be allowlisted.
 *
 * TODO(production): this must not ship as-is. Captures of a subject's face and
 * identity document currently cross the local network unencrypted and
 * unauthenticated. Serve the screening service over TLS with a certificate
 * pinned by device management, then remove the cleartext permission.
 */

function fromExpoConfig(): string | null {
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  const value = extra?.screeningServiceUrl;
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function fromEnvironment(): string | null {
  // Inlined by Metro at build time; lets a build be pointed at a service
  // without editing app.json.
  const value = process.env.EXPO_PUBLIC_SCREENING_SERVICE_URL;
  return typeof value === 'string' && value.length > 0 ? value : null;
}

/** The address a build ships with, before any officer override. */
export const CONFIGURED_SCREENING_SERVICE_URL: string | null =
  fromEnvironment() ?? fromExpoConfig();

/**
 * Rejects anything that is not a usable http(s) origin.
 *
 * A half-typed address should fall back to the configured one rather than
 * produce a request that cannot succeed, so the officer sees "no service
 * configured" rather than a network error with no explanation.
 */
export function normaliseServiceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) return null;
  if (!/^https?:\/\/[^\s/]+/i.test(trimmed)) return null;
  return trimmed;
}

/** The address to use, preferring an officer override over the build default. */
export function resolveScreeningServiceUrl(override?: string | null): string | null {
  return normaliseServiceUrl(override) ?? normaliseServiceUrl(CONFIGURED_SCREENING_SERVICE_URL);
}
