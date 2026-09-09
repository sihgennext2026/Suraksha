import { z } from 'zod';

/**
 * Sign-in validation.
 *
 * These rules mirror the format the enrolment service issues, so a typo is
 * caught before it becomes a failed authentication attempt — which matters when
 * repeated failures will eventually lock the device.
 */
export const loginSchema = z.object({
  officerId: z
    .string()
    .trim()
    .min(1, 'Enter your officer ID')
    .regex(/^[A-Za-z]{3}\d{4}$/, 'Officer IDs are three letters followed by four digits'),
  pin: z
    .string()
    .min(4, 'Your PIN is at least 4 digits')
    .max(8, 'Your PIN is at most 8 digits')
    .regex(/^\d+$/, 'Your PIN contains digits only'),
});

export type LoginFormValues = z.infer<typeof loginSchema>;
