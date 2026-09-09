const reactNativeResolver = require('react-native/jest/resolver');

/**
 * Module resolution for tests.
 *
 * `react-native-worklets` ships `.native.ts` implementations that call into the
 * JSI runtime, which does not exist under Jest. Dropping the `native` extension
 * for anything resolved from inside that package makes Jest pick its plain
 * JavaScript implementations instead, which is what lets Reanimated's own test
 * mock load. Everything else falls through to React Native's resolver
 * unchanged.
 */
module.exports = (request, options) => {
  const fromWorklets =
    options.basedir.includes('react-native-worklets') || request.includes('react-native-worklets');

  if (fromWorklets && Array.isArray(options.extensions)) {
    return reactNativeResolver(request, {
      ...options,
      extensions: options.extensions.filter((extension) => !extension.includes('native')),
    });
  }

  return reactNativeResolver(request, options);
};
