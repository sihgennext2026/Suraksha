const { withAndroidManifest } = require('expo/config-plugins');

/**
 * Permits plain-HTTP requests to the screening service.
 *
 * Android 9 (API 28) and later refuse cleartext traffic by default, and the
 * refusal happens inside the platform before a packet leaves the device: the
 * request fails instantly, the service logs nothing at all, and the officer sees
 * only "Screening stopped". That failure mode is silent enough to be worth this
 * comment — nothing on the server side hints that the phone ever tried.
 *
 * The screening service speaks HTTP on a post's local network. Android's network
 * security config can exempt named hosts but not private address ranges, and the
 * service's address changes with the network it is on, so there is no narrower
 * exemption to write than this one.
 *
 * Expo has no `android.usesCleartextTraffic` config key, so this sets the
 * manifest attribute directly. `android/` is generated and gitignored, so doing
 * it by hand would be lost on the next prebuild.
 *
 * TODO(production): this must not ship. Captures of a subject's face and
 * identity document currently cross the local network unencrypted and
 * unauthenticated, readable by anything else on that network. Serve the
 * screening service over TLS with a certificate pinned through device
 * management, then delete this plugin.
 */
module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, (mod) => {
    const application = mod.modResults.manifest?.application?.[0];
    if (!application) {
      throw new Error('withCleartextTraffic: no <application> element in the manifest');
    }
    application.$['android:usesCleartextTraffic'] = 'true';
    return mod;
  });
};
