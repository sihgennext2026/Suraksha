import { useEffect, useState } from 'react';

import type { CaptureFeedbackTone } from '@/components/overlay/CaptureOverlay';

export interface LiveFeedback {
  tone: CaptureFeedbackTone;
  headline: string;
  instruction: string;
  checks: { label: string; ok: boolean }[];
  /** True once the frame is good enough that capture is advisable. */
  ready: boolean;
}

type Subject = 'DOCUMENT' | 'FACE';

/**
 * Live capture feedback.
 *
 * The production build runs the detector on the preview stream. Until that
 * exists, this hook models the same sequence an officer sees while lining a
 * document up: nothing found, then partially in frame, then framed and steady.
 * It advances on a timer rather than randomly, so the guidance never flickers
 * between states and never contradicts itself.
 *
 * What matters for the interface is that every state names the correction. The
 * screen this drives is the one the real detector will drive unchanged.
 */
const DOCUMENT_SEQUENCE: LiveFeedback[] = [
  {
    tone: 'blocked',
    headline: 'Document not detected',
    instruction: 'Place the document flat inside the frame.',
    checks: [
      { label: 'Document in frame', ok: false },
      { label: 'Fills the guide', ok: false },
      { label: 'Sharp and glare-free', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'adjusting',
    headline: 'Document partially in frame',
    instruction: 'Move the camera closer so the document fills the guide.',
    checks: [
      { label: 'Document in frame', ok: true },
      { label: 'Fills the guide', ok: false },
      { label: 'Sharp and glare-free', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'adjusting',
    headline: 'Hold steady',
    instruction: 'Almost there. Keep the device still while the edges settle.',
    checks: [
      { label: 'Document in frame', ok: true },
      { label: 'Fills the guide', ok: true },
      { label: 'Sharp and glare-free', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'ready',
    headline: 'Document detected',
    instruction: 'Quality and position are good. Capture now.',
    checks: [
      { label: 'Document in frame', ok: true },
      { label: 'Fills the guide', ok: true },
      { label: 'Sharp and glare-free', ok: true },
    ],
    ready: true,
  },
];

const FACE_SEQUENCE: LiveFeedback[] = [
  {
    tone: 'blocked',
    headline: 'No face detected',
    instruction: 'Ask the subject to look directly at the camera.',
    checks: [
      { label: 'One face detected', ok: false },
      { label: 'Facing the camera', ok: false },
      { label: 'Evenly lit', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'adjusting',
    headline: 'Face detected',
    instruction: 'Bring the face inside the oval and hold still.',
    checks: [
      { label: 'One face detected', ok: true },
      { label: 'Facing the camera', ok: false },
      { label: 'Evenly lit', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'adjusting',
    headline: 'Adjust lighting',
    instruction: 'Move out of direct backlight, or step towards the light.',
    checks: [
      { label: 'One face detected', ok: true },
      { label: 'Facing the camera', ok: true },
      { label: 'Evenly lit', ok: false },
    ],
    ready: false,
  },
  {
    tone: 'ready',
    headline: 'One face detected',
    instruction: 'Quality is good. Capture now.',
    checks: [
      { label: 'One face detected', ok: true },
      { label: 'Facing the camera', ok: true },
      { label: 'Evenly lit', ok: true },
    ],
    ready: true,
  },
];

const STEP_INTERVAL_MS = 850;

export function useLiveCaptureFeedback(subject: Subject, active: boolean): LiveFeedback {
  const sequence = subject === 'DOCUMENT' ? DOCUMENT_SEQUENCE : FACE_SEQUENCE;
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!active) return;
    // State is advanced only from the interval callback, and it stops at the
    // final entry. While the sequence is paused — during a capture, say — the
    // last state persists rather than resetting, which is what the officer
    // would expect from a detector that simply stopped reporting.
    const id = setInterval(
      () => setStep((current) => Math.min(current + 1, sequence.length - 1)),
      STEP_INTERVAL_MS,
    );
    return () => clearInterval(id);
  }, [active, sequence.length]);

  return sequence[Math.min(step, sequence.length - 1)] as LiveFeedback;
}
