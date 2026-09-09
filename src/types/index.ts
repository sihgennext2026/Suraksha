/**
 * Application types.
 *
 * Service results are NOT defined here — they live in `@/contracts`, which is a
 * mirror of the canonical wire schema. This module re-exports the contract
 * types for convenience so a screen has one import, but the definitions belong
 * to the contract.
 */

export * from '@/contracts';

export * from './common';
export * from './document';
export * from './auth';
export * from './case';
