import type { ModuleName } from '@/contracts';
import type { ScreeningStageId } from '@/types/case';

/**
 * Pipeline stage presentation.
 *
 * No threshold lives in this file. Every boundary, band and weight comes from
 * `@/config/thresholds`, which reads the shared configuration the Python
 * services read. This module only describes what the officer is watching.
 */

interface StageDescriptor {
  id: ScreeningStageId;
  label: string;
  /** What this stage does, in one line, for the progress screen. */
  description: string;
  /** Which engine performs the work. Shown in analysis details. */
  engine: string;
  /**
   * Which contract module this stage reports through, if any. The two
   * preprocessing stages produce no module envelope of their own — their
   * outcome is folded into the OCR result.
   */
  module: ModuleName | null;
}

export const SCREENING_STAGE_DESCRIPTORS: Record<ScreeningStageId, StageDescriptor> = {
  DOCUMENT_DETECTION: {
    id: 'DOCUMENT_DETECTION',
    label: 'Document detection',
    description: 'Locating the document within the captured frame',
    engine: 'U-Net segmentation',
    module: 'ocr',
  },
  DOCUMENT_PROCESSING: {
    id: 'DOCUMENT_PROCESSING',
    label: 'Document processing',
    description: 'Correcting orientation and rectifying perspective',
    engine: 'Orientation + homography',
    module: 'ocr',
  },
  OCR_MRZ: {
    id: 'OCR_MRZ',
    label: 'OCR and MRZ',
    description: 'Extracting printed fields and reading the machine-readable zone',
    engine: 'PP-OCRv5',
    module: 'ocr',
  },
  RULE_VALIDATION: {
    id: 'RULE_VALIDATION',
    label: 'Rule validation',
    description: 'Applying deterministic consistency and checksum rules',
    engine: 'Rule engine',
    module: 'validation',
  },
  FACE_VERIFICATION: {
    id: 'FACE_VERIFICATION',
    label: 'Face verification',
    description: 'Comparing the document portrait against the subject capture',
    engine: 'ArcFace R50',
    module: 'face_verification',
  },
  DOCUMENT_FORENSICS: {
    id: 'DOCUMENT_FORENSICS',
    label: 'Document forensics',
    description: 'Examining the document for tampering',
    engine: 'DINOv2 ViT-B/14',
    module: 'document_forensics',
  },
  ANOMALY_ANALYSIS: {
    id: 'ANOMALY_ANALYSIS',
    label: 'Anomaly analysis',
    description: 'Measuring deviation from genuine reference documents',
    engine: 'PatchCore',
    module: 'anomaly',
  },
  RISK_ASSESSMENT: {
    id: 'RISK_ASSESSMENT',
    label: 'Risk assessment',
    description: 'Combining all available evidence into a graded assessment',
    engine: 'Evidence Fusion Engine',
    module: 'risk',
  },
};

/** Officer-facing name of each contract module. */
export const MODULE_LABELS: Record<ModuleName, string> = {
  ocr: 'Field extraction',
  validation: 'Rule validation',
  face_verification: 'Face verification',
  document_forensics: 'Document forensics',
  anomaly: 'Anomaly analysis',
  risk: 'Risk assessment',
};
