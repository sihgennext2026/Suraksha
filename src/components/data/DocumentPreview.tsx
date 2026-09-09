import React, { useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Image } from 'expo-image';

import { Text } from '@/components/primitives/Text';
import { useTheme } from '@/theme';
import type { BoundingBox } from '@/contracts';

/** A region drawn over the document, with the meaning the officer needs. */
export interface PreviewRegion {
  id: string;
  /** `[x, y, width, height]`, normalised against the corrected document image. */
  box: BoundingBox;
  /** 0..1. Drives the overlay tone: higher means more suspicious. */
  severity: number;
  /** Short label drawn on the region, e.g. `1`. */
  marker: string;
  /** Full description, shown when the region is selected. */
  note: string;
  /** What kind of finding this is, e.g. `Photo replacement`. */
  category: string;
}

interface DocumentPreviewProps {
  uri: string;
  /** Width divided by height. Keeps the overlay aligned with the image. */
  aspectRatio?: number;
  regions?: PreviewRegion[];
  /** Selected region id. Uncontrolled when omitted. */
  selectedRegionId?: string | null;
  onSelectRegion?: (id: string | null) => void;
  /** Draws the detection bounding box. */
  detectionBox?: BoundingBox | null;
  contentFit?: 'contain' | 'cover';
  accessibilityLabel?: string;
}

/**
 * A document image with findings drawn on it.
 *
 * The whole point of the forensics and anomaly screens is to answer *where*, so
 * the regions are drawn on the document itself rather than listed beside it.
 * Tapping a region reveals what was found there; nothing is hidden behind a
 * legend the officer has to decode.
 */
export function DocumentPreview({
  uri,
  aspectRatio = 1.42,
  regions = [],
  selectedRegionId,
  onSelectRegion,
  detectionBox,
  contentFit = 'contain',
  accessibilityLabel = 'Captured document',
}: DocumentPreviewProps) {
  const theme = useTheme();
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [internalSelection, setInternalSelection] = useState<string | null>(null);

  const selected = selectedRegionId !== undefined ? selectedRegionId : internalSelection;

  function handleLayout(event: LayoutChangeEvent) {
    const { width, height } = event.nativeEvent.layout;
    setSize({ width, height });
  }

  function select(id: string | null) {
    if (onSelectRegion) onSelectRegion(id);
    else setInternalSelection(id);
  }

  function heatColour(severity: number): string {
    if (severity >= 0.6) return theme.color.heatHigh;
    if (severity >= 0.3) return theme.color.heatMedium;
    return theme.color.heatLow;
  }

  function borderColour(severity: number): string {
    if (severity >= 0.6) return theme.color.critical;
    if (severity >= 0.3) return theme.color.caution;
    return theme.color.info;
  }

  const activeRegion = regions.find((region) => region.id === selected) ?? null;

  return (
    <View>
      <View
        onLayout={handleLayout}
        style={[
          styles.frame,
          {
            aspectRatio,
            backgroundColor: theme.color.surfaceSunken,
            borderColor: theme.color.border,
            borderWidth: theme.borderWidth.thin,
            borderRadius: theme.radii.lg,
          },
        ]}
      >
        <Image
          source={{ uri }}
          style={StyleSheet.absoluteFill}
          contentFit={contentFit}
          transition={160}
          accessible
          accessibilityLabel={accessibilityLabel}
        />

        {detectionBox && size.width > 0 ? (
          <View
            pointerEvents="none"
            style={{
              position: 'absolute',
              left: detectionBox[0] * size.width,
              top: detectionBox[1] * size.height,
              width: detectionBox[2] * size.width,
              height: detectionBox[3] * size.height,
              borderWidth: theme.borderWidth.medium,
              borderColor: theme.color.accent,
              borderRadius: theme.radii.xs,
            }}
          />
        ) : null}

        {size.width > 0
          ? regions.map((region) => {
              const isActive = region.id === selected;
              return (
                <Pressable
                  key={region.id}
                  onPress={() => select(isActive ? null : region.id)}
                  accessibilityRole="button"
                  accessibilityLabel={`${region.category} region ${region.marker}. ${region.note}`}
                  accessibilityState={{ selected: isActive }}
                  style={{
                    position: 'absolute',
                    left: region.box[0] * size.width,
                    top: region.box[1] * size.height,
                    width: region.box[2] * size.width,
                    height: region.box[3] * size.height,
                    backgroundColor: heatColour(region.severity),
                    borderWidth: isActive ? theme.borderWidth.thick : theme.borderWidth.medium,
                    borderColor: borderColour(region.severity),
                    borderRadius: theme.radii.xs,
                  }}
                >
                  <View
                    style={[
                      styles.marker,
                      {
                        backgroundColor: borderColour(region.severity),
                        borderRadius: theme.radii.xs,
                      },
                    ]}
                  >
                    <Text
                      role="monoSmall"
                      weight="bold"
                      style={{ color: theme.color.textOnAccent, fontSize: 10 }}
                      accessible={false}
                    >
                      {region.marker}
                    </Text>
                  </View>
                </Pressable>
              );
            })
          : null}
      </View>

      {regions.length > 0 ? (
        <View
          style={[
            styles.caption,
            {
              marginTop: theme.spacing.sm,
              backgroundColor: theme.color.surfaceSunken,
              borderColor: theme.color.border,
              borderWidth: theme.borderWidth.thin,
              borderRadius: theme.radii.md,
              padding: theme.spacing.md,
            },
          ]}
        >
          {activeRegion ? (
            <>
              <Text role="label" tone="tertiary">
                Region {activeRegion.marker} · {activeRegion.category}
              </Text>
              <Text role="caption" tone="secondary" style={{ marginTop: theme.spacing.xs }}>
                {activeRegion.note}
              </Text>
            </>
          ) : (
            <Text role="caption" tone="tertiary">
              {regions.length === 1
                ? 'One region was flagged. Tap it to see what was found there.'
                : `${regions.length} regions were flagged. Tap one to see what was found there.`}
            </Text>
          )}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { width: '100%', overflow: 'hidden' },
  marker: {
    position: 'absolute',
    top: -1,
    left: -1,
    minWidth: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  caption: {},
});
