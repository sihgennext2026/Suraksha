const expoConfig = require('eslint-config-expo/flat');
const prettierConfig = require('eslint-config-prettier');
const typescriptEslint = require('typescript-eslint');

/**
 * Lint configuration.
 *
 * The rules added on top of the Expo preset are the ones that protect decisions
 * made elsewhere in this codebase: no `any` (the domain model is the contract
 * between the mock and the future backend), and no stray `console` calls (all
 * diagnostics go through the redacting logger so personal data cannot leak into
 * a log sink).
 */
module.exports = [
  ...expoConfig,
  prettierConfig,
  {
    ignores: ['node_modules/**', '.expo/**', 'dist/**', 'coverage/**', 'android/**', 'ios/**'],
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    plugins: { '@typescript-eslint': typescriptEslint.plugin },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
  {
    // The logger is the one place permitted to reach the console directly.
    files: ['src/utils/logger.ts'],
    rules: { 'no-console': 'off' },
  },
  {
    /**
     * Test setup necessarily breaks two rules that are right everywhere else.
     * `jest.mock` factories must be declared above the imports they intercept
     * (Babel hoists them regardless, so writing them below would be misleading),
     * and those factories can only reach a module through `require`.
     */
    files: ['__tests__/**/*.{ts,tsx}', 'jest.setup.ts'],
    rules: {
      'import/first': 'off',
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
];
