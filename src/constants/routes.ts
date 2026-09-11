/**
 * Every navigation target in the application. Screens import from here rather
 * than writing path literals, so a route rename is a single edit.
 */
export const ROUTES = {
  boot: '/',
  auth: {
    login: '/(auth)/login',
    deviceSetup: '/(auth)/device-setup',
  },
  app: {
    dashboard: '/(app)/dashboard',
    cases: '/(app)/cases',
    settings: '/(app)/settings',
  },
  screening: {
    documentType: '/screening/document-type',
    documentCapture: '/screening/document-capture',
    documentBackCapture: '/screening/document-back-capture',
    documentReview: '/screening/document-review',
    personCapture: '/screening/person-capture',
    progress: '/screening/progress',
    result: '/screening/result',
    evidence: '/screening/evidence',
    decision: '/screening/decision',
    ocr: '/screening/ocr',
    validation: '/screening/validation',
    face: '/screening/face',
    forensics: '/screening/forensics',
    anomaly: '/screening/anomaly',
  },
  caseDetail: (id: string) => `/case/${id}` as const,
} as const;

/** Ordered screening route sequence, used to resume an interrupted case. */
export const SCREENING_FLOW_ORDER = [
  ROUTES.screening.documentType,
  ROUTES.screening.documentCapture,
  ROUTES.screening.documentReview,
  ROUTES.screening.personCapture,
  ROUTES.screening.progress,
  ROUTES.screening.result,
] as const;
