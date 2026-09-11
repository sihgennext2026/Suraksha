import React from 'react';

import { DocumentCaptureScreen } from '@/features/document/screens/DocumentCaptureScreen';

/**
 * The reverse of the document.
 *
 * The same camera as the front, told which side it is photographing. Reaching
 * this screen is optional: the officer can go straight from the review to the
 * subject capture, and the merge then reports whatever the reverse was expected
 * to carry as REVIEW rather than treating the case as incomplete.
 */
export default function DocumentBackCaptureRoute() {
  return <DocumentCaptureScreen side="back" />;
}
