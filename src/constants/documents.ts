import type { DocumentType } from '@/contracts';
import type { DocumentTypeDescriptor } from '@/types/document';

/**
 * Officer-facing presentation of each canonical document type.
 *
 * `backendSupported` is the honest half of this table. Two of the seven types
 * have no extraction schema and no validation rule set. They are still offered:
 * an officer meeting a document outside the five needs somewhere to put it, and
 * removing the option would push them into declaring the wrong type — which
 * would run the wrong rules and produce a confident, wrong answer. Instead the
 * capture screen says the type is unsupported, and the screening reports those
 * modules as NOT_AVAILABLE rather than borrowing another type's rules.
 */
export const DOCUMENT_TYPE_DESCRIPTORS: Record<DocumentType, DocumentTypeDescriptor> = {
  passport: {
    type: 'passport',
    label: 'Passport',
    hint: 'Booklet biodata page with machine-readable zone',
    hasMrz: true,
    hasBackFields: false,
    captureAspectRatio: 125 / 88,
    backendSupported: true,
  },
  visa: {
    type: 'visa',
    label: 'Visa',
    hint: 'Visa sticker or label affixed inside a travel document',
    hasMrz: true,
    hasBackFields: false,
    captureAspectRatio: 105 / 74,
    backendSupported: true,
  },
  national_id: {
    type: 'national_id',
    label: 'National identity card',
    hint: 'Government-issued identity card, front face',
    hasMrz: false,
    hasBackFields: true,
    captureAspectRatio: 85.6 / 54,
    backendSupported: true,
  },
  driving_license: {
    type: 'driving_license',
    label: 'Driving licence',
    hint: 'Card-format driving licence, front face',
    hasMrz: false,
    hasBackFields: true,
    captureAspectRatio: 85.6 / 54,
    backendSupported: true,
  },
  permit: {
    type: 'permit',
    label: 'Permit',
    hint: 'Border, residence, labour or movement permit',
    hasMrz: false,
    hasBackFields: true,
    captureAspectRatio: 85.6 / 54,
    backendSupported: true,
  },
  travel_authorization: {
    type: 'travel_authorization',
    label: 'Travel authorisation',
    hint: 'Printed authorisation, e-visa or transit clearance',
    hasMrz: false,
    hasBackFields: false,
    captureAspectRatio: 297 / 210,
    backendSupported: false,
  },
  other: {
    type: 'other',
    label: 'Other document',
    hint: 'Any other identity or travel document',
    hasMrz: false,
    hasBackFields: false,
    captureAspectRatio: 85.6 / 54,
    backendSupported: false,
  },
};

export function documentTypeLabel(type: DocumentType): string {
  return DOCUMENT_TYPE_DESCRIPTORS[type].label;
}

/** Officer-facing explanation shown when an unsupported type is selected. */
export const UNSUPPORTED_TYPE_NOTICE =
  'Field extraction and rule validation do not support this document type. ' +
  'Face verification and tamper detection still run, and the screening will ' +
  'state plainly which checks were not performed.';
