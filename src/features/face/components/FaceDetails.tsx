import React from 'react';
import { StyleSheet, View } from 'react-native';

import { Panel, Section } from '@/components/layout/Panel';
import { Text } from '@/components/primitives/Text';
import { FaceComparison } from '@/components/data/FaceComparison';
import { KeyValueRow } from '@/components/data/KeyValueRow';
import { FaceDecisionBadge } from '@/components/data/StatusBadge';
import { FACE_DECISION_PRESENTATION } from '@/constants/labels';
import { FACE_THRESHOLD_PROVENANCE } from '@/config/thresholds';
import { useTheme } from '@/theme';
import type { Envelope, FaceVerificationResult } from '@/contracts';

interface FaceDetailsProps {
  envelope: Envelope<FaceVerificationResult>;
  result: FaceVerificationResult;
  documentImageUri: string;
  personImageUri: string;
  showProvenance?: boolean;
}

/**
 * 1:1 face verification.
 *
 * The number on this screen is a RAW cosine similarity between two 512-D
 * ArcFace embeddings. It is not a probability and not a percentage, and it is
 * shown as the model produced it — `0.31`, never `31%`. The application knows
 * nothing about what the value means; the decision arrived with the result, and
 * the boundaries are shown beside it so an officer can see how close the call
 * was rather than having to trust a bare verdict.
 */
export function FaceDetails({
  envelope,
  result,
  documentImageUri,
  personImageUri,
  showProvenance = true,
}: FaceDetailsProps) {
  const theme = useTheme();
  const presentation = FACE_DECISION_PRESENTATION[result.decision];

  const decisionColour = {
    MATCH: theme.color.positive,
    REVIEW: theme.color.caution,
    NO_MATCH: theme.color.critical,
  }[result.decision];

  const tone =
    result.decision === 'MATCH'
      ? 'positive'
      : result.decision === 'REVIEW'
        ? 'caution'
        : 'critical';

  const explanation = {
    MATCH:
      `The similarity is at or above the ${result.thresholds.match.toFixed(2)} match ` +
      'boundary. The subject and the document portrait are the same person, to the ' +
      'confidence this comparison can provide.',
    REVIEW:
      `The similarity falls between the ${result.thresholds.review.toFixed(2)} and ` +
      `${result.thresholds.match.toFixed(2)} boundaries. Ageing, pose and portrait ` +
      'quality all push scores into this range, so the comparison is not decisive on ' +
      'its own and needs a human look.',
    NO_MATCH:
      `The similarity is below the ${result.thresholds.review.toFixed(2)} boundary. ` +
      'Scores this low are not normally produced by the same person.',
  }[result.decision];

  return (
    <>
      <Panel tone={tone} style={{ marginTop: theme.spacing.lg }}>
        <View style={styles.verdictRow}>
          <Text role="title" weight="bold" style={{ color: decisionColour }} accessible={false}>
            {presentation.glyph}
          </Text>
          <Text
            role="title"
            style={{ color: decisionColour }}
            accessibilityRole="header"
            accessibilityLabel={presentation.a11yLabel}
          >
            {presentation.label.toUpperCase()}
          </Text>
        </View>

        <View style={[styles.scoreRow, { marginTop: theme.spacing.lg }]}>
          <View>
            <Text role="label" tone="tertiary">
              Cosine similarity
            </Text>
            {/*
              Shown to two decimal places, unscaled and unsuffixed. Rendering
              this as a percentage would assert a calibration the model does not
              have.
            */}
            <Text
              role="headline"
              style={{ color: decisionColour, marginTop: 2 }}
              accessibilityLabel={`Cosine similarity ${result.similarity.toFixed(2)}`}
            >
              {result.similarity.toFixed(2)}
            </Text>
            <Text role="caption" tone="tertiary" style={{ marginTop: 2 }}>
              Raw model score, not a percentage
            </Text>
          </View>
        </View>

        <SimilarityScale
          similarity={result.similarity}
          review={result.thresholds.review}
          match={result.thresholds.match}
        />

        <Text role="body" tone="secondary" style={{ marginTop: theme.spacing.lg }}>
          {explanation}
        </Text>
      </Panel>

      <Section title="Comparison" description="Look at both images before accepting the score.">
        <FaceComparison
          documentSample={{
            uri: documentImageUri,
            label: 'Document portrait',
            quality: result.quality.document_face,
          }}
          liveSample={{
            uri: personImageUri,
            label: 'Subject capture',
            quality: result.quality.live_face,
          }}
        />
      </Section>

      {showProvenance ? (
        <Section title="Analysis details">
          <Panel padded={false}>
            <KeyValueRow label="Model" value={envelope.model_version} mono />
            <KeyValueRow
              label="Embedding"
              value={`${result.embedding_dim ?? 512}-D, L2 normalised`}
              mono
            />
            <KeyValueRow
              label="Match boundary"
              value={`At or above ${result.thresholds.match.toFixed(2)}`}
              mono
            />
            <KeyValueRow
              label="No-match boundary"
              value={`Below ${result.thresholds.review.toFixed(2)}`}
              mono
            />
            <KeyValueRow label="Status" value={envelope.status} mono />
          </Panel>

          {/*
            The thresholds are provisional and the provenance says so verbatim.
            A number quoted without its confidence invites an officer to treat a
            calibration boundary as settled fact.
          */}
          <Panel tone="sunken" style={{ marginTop: theme.spacing.md }}>
            <Text role="label" tone="tertiary">
              How these boundaries were set
            </Text>
            <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
              {FACE_THRESHOLD_PROVENANCE.calibration}
            </Text>
            <Text role="caption" tone="caution" style={{ marginTop: theme.spacing.sm }}>
              {FACE_THRESHOLD_PROVENANCE.confidence}
            </Text>
          </Panel>
        </Section>
      ) : null}
    </>
  );
}

/**
 * The similarity drawn against its decision bands.
 *
 * The scale runs 0..1 across the cosine range that matters in practice. A bare
 * number invites an officer to invent their own threshold; showing where it
 * falls makes a borderline result look borderline.
 */
function SimilarityScale({
  similarity,
  review,
  match,
}: {
  similarity: number;
  review: number;
  match: number;
}) {
  const theme = useTheme();
  const position = Math.max(0, Math.min(1, similarity));

  return (
    <View
      style={{ marginTop: theme.spacing.lg }}
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={`Similarity ${similarity.toFixed(2)}. No match below ${review.toFixed(
        2,
      )}, review from ${review.toFixed(2)}, match at or above ${match.toFixed(2)}.`}
    >
      <View style={[styles.track, { borderRadius: theme.radii.xs }]}>
        <View style={{ flex: review, backgroundColor: theme.color.criticalSubtle }} />
        <View style={{ flex: match - review, backgroundColor: theme.color.cautionSubtle }} />
        <View style={{ flex: 1 - match, backgroundColor: theme.color.positiveSubtle }} />
        <View
          style={[
            styles.marker,
            { left: `${position * 100}%`, backgroundColor: theme.color.textPrimary },
          ]}
        />
      </View>
      <View style={[styles.scaleLabels, { marginTop: theme.spacing.xs }]}>
        <Text role="monoSmall" tone="tertiary">
          0.00
        </Text>
        <Text role="monoSmall" tone="tertiary">
          {review.toFixed(2)} review
        </Text>
        <Text role="monoSmall" tone="tertiary">
          {match.toFixed(2)} match
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  verdictRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  scoreRow: { flexDirection: 'row', gap: 32 },
  track: { flexDirection: 'row', height: 8, overflow: 'visible', position: 'relative' },
  marker: { position: 'absolute', top: -4, width: 3, height: 16, marginLeft: -1.5, borderRadius: 2 },
  scaleLabels: { flexDirection: 'row', justifyContent: 'space-between' },
});

export { FaceDecisionBadge };
