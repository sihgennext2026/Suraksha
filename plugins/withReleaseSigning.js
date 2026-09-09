const fs = require('node:fs');
const path = require('node:path');

const {
  withAppBuildGradle,
  withGradleProperties,
} = require('expo/config-plugins');

/**
 * Signs release builds with the project keystore instead of the debug key.
 *
 * `android/` is generated and gitignored, so editing the Gradle files by hand
 * loses the change on the next `expo prebuild --clean`. This plugin reapplies it
 * every time the native project is generated, which is what makes a signed build
 * reproducible rather than a one-off on one machine.
 *
 * The keystore and its passwords live in `credentials/`, untracked. When that
 * directory is absent — a fresh clone, or CI without the secrets mounted — the
 * build falls back to the debug key rather than failing, so `assembleDebug` and
 * `run:android` keep working for anyone who only wants to run the app.
 *
 * TODO(production): replace the local keystore with managed credentials. A key
 * that sits unencrypted next to the source is acceptable for field trials, not
 * for an operational release.
 */

const CREDENTIALS_DIR = 'credentials';
const PROPERTIES_FILE = 'android-signing.properties';

/** The Gradle property names this plugin bridges from the untracked file. */
const REQUIRED_KEYS = [
  'SSB_RELEASE_STORE_FILE',
  'SSB_RELEASE_KEY_ALIAS',
  'SSB_RELEASE_STORE_PASSWORD',
  'SSB_RELEASE_KEY_PASSWORD',
];

/**
 * Reads the untracked signing properties, or returns null when they are not
 * present. Environment variables win, so CI can supply the same values without
 * writing a file to disk.
 */
function readSigningConfig(projectRoot) {
  const fromEnv = {};
  for (const key of REQUIRED_KEYS) {
    if (process.env[key]) fromEnv[key] = process.env[key];
  }
  if (REQUIRED_KEYS.every((key) => fromEnv[key])) return fromEnv;

  const file = path.join(projectRoot, CREDENTIALS_DIR, PROPERTIES_FILE);
  if (!fs.existsSync(file)) return null;

  const fromFile = {};
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const separator = trimmed.indexOf('=');
    if (separator === -1) continue;
    fromFile[trimmed.slice(0, separator).trim()] = trimmed.slice(separator + 1).trim();
  }

  const merged = { ...fromFile, ...fromEnv };
  const missing = REQUIRED_KEYS.filter((key) => !merged[key]);
  if (missing.length > 0) {
    // Half a configuration is a misconfiguration, and silently producing a
    // debug-signed APK from it would be worse than saying so.
    throw new Error(
      `${CREDENTIALS_DIR}/${PROPERTIES_FILE} is missing: ${missing.join(', ')}`,
    );
  }

  // `storeFile` is resolved by Gradle relative to android/app, so an entry that
  // names a bare file is taken to sit next to the properties file.
  const store = merged.SSB_RELEASE_STORE_FILE;
  merged.SSB_RELEASE_STORE_FILE = path.isAbsolute(store)
    ? store
    : path.join(projectRoot, CREDENTIALS_DIR, store);

  if (!fs.existsSync(merged.SSB_RELEASE_STORE_FILE)) {
    throw new Error(`Keystore not found: ${merged.SSB_RELEASE_STORE_FILE}`);
  }

  return merged;
}

/** Declares the `release` signing config next to the generated `debug` one. */
function addSigningConfig(contents) {
  const anchor = `    signingConfigs {
        debug {`;
  if (!contents.includes(anchor)) {
    throw new Error('Unexpected android/app/build.gradle: signingConfigs block not found');
  }
  return contents.replace(
    anchor,
    `    signingConfigs {
        release {
            storeFile file(SSB_RELEASE_STORE_FILE)
            storePassword SSB_RELEASE_STORE_PASSWORD
            keyAlias SSB_RELEASE_KEY_ALIAS
            keyPassword SSB_RELEASE_KEY_PASSWORD
        }
        debug {`,
  );
}

/** Points the release build type at that config. */
function useSigningConfigForRelease(contents) {
  const anchor = `            signingConfig signingConfigs.debug`;
  const occurrences = contents.split(anchor).length - 1;
  if (occurrences !== 2) {
    throw new Error(
      `Unexpected android/app/build.gradle: expected 2 debug signingConfig references, found ${occurrences}`,
    );
  }
  // The first occurrence belongs to the debug build type; only the second, in
  // the release block, is replaced.
  const releaseIndex = contents.indexOf(anchor, contents.indexOf(anchor) + 1);
  return (
    contents.slice(0, releaseIndex) +
    `            signingConfig signingConfigs.release` +
    contents.slice(releaseIndex + anchor.length)
  );
}

module.exports = function withReleaseSigning(config) {
  // Read in each mod rather than once up front: the mod compiler decides the
  // order these run in, and neither should depend on the other having gone
  // first to know whether signing is configured.
  config = withGradleProperties(config, (mod) => {
    const signing = readSigningConfig(mod.modRequest.projectRoot);
    if (!signing) return mod;

    for (const key of REQUIRED_KEYS) {
      const existing = mod.modResults.findIndex(
        (item) => item.type === 'property' && item.key === key,
      );
      // Gradle escapes backslashes in property values, so a Windows path has to
      // be written with forward slashes to survive the round trip.
      const value = signing[key].split('\\').join('/');
      const entry = { type: 'property', key, value };
      if (existing === -1) mod.modResults.push(entry);
      else mod.modResults[existing] = entry;
    }
    return mod;
  });

  return withAppBuildGradle(config, (mod) => {
    if (!readSigningConfig(mod.modRequest.projectRoot)) return mod;
    if (mod.modResults.language !== 'groovy') {
      throw new Error('withReleaseSigning expects a Groovy build.gradle');
    }
    if (mod.modResults.contents.includes('signingConfigs.release')) return mod;

    mod.modResults.contents = useSigningConfigForRelease(
      addSigningConfig(mod.modResults.contents),
    );
    return mod;
  });
};
