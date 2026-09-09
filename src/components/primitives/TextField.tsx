import React, { forwardRef, useState } from 'react';
import {
  Pressable,
  StyleSheet,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';

import { useTheme } from '@/theme';

import { Text } from './Text';

export interface TextFieldProps extends Omit<TextInputProps, 'style' | 'role'> {
  /** Style applied to the input itself, e.g. a taller box for remarks. */
  inputStyle?: StyleProp<TextStyle>;
  label: string;
  /** Officer-facing validation message. Presence switches the field to error. */
  error?: string;
  /** Guidance shown under the field when there is no error. */
  hint?: string;
  /** Monospaces the input, for identifiers and codes. */
  mono?: boolean;
  /** Adds a show/hide control. Used for the PIN field. */
  secure?: boolean;
  /** Trailing adornment, e.g. a character counter. */
  trailing?: React.ReactNode;
  containerStyle?: StyleProp<ViewStyle>;
  required?: boolean;
}

/**
 * A labelled text input.
 *
 * The label sits above the field rather than inside it: a floating label
 * disappears exactly when an officer is mid-entry and most likely to need it,
 * and it makes the error message's relationship to the field ambiguous.
 */
export const TextField = forwardRef<TextInput, TextFieldProps>(function TextField(
  {
    label,
    error,
    hint,
    mono = false,
    secure = false,
    trailing,
    containerStyle,
    inputStyle,
    required = false,
    onFocus,
    onBlur,
    ...rest
  },
  ref,
) {
  const theme = useTheme();
  const [focused, setFocused] = useState(false);
  const [revealed, setRevealed] = useState(false);

  const borderColour = error
    ? theme.color.critical
    : focused
      ? theme.color.borderFocus
      : theme.color.border;

  return (
    <View style={containerStyle}>
      <View style={styles.labelRow}>
        <Text role="label" tone="tertiary">
          {label}
        </Text>
        {required ? (
          <Text role="label" tone="tertiary">
            Required
          </Text>
        ) : null}
      </View>

      <View
        style={[
          styles.field,
          {
            marginTop: theme.spacing.xs,
            backgroundColor: theme.color.surfaceSunken,
            borderColor: borderColour,
            borderWidth: focused || error ? theme.borderWidth.medium : theme.borderWidth.thin,
            borderRadius: theme.radii.md,
            minHeight: theme.controlHeight.large,
            paddingHorizontal: theme.spacing.md,
          },
        ]}
      >
        <TextInput
          ref={ref}
          style={[
            styles.input,
            {
              color: theme.color.textPrimary,
              fontSize: theme.fontSize.bodyLarge,
              fontFamily: mono ? theme.fontFamily.mono : undefined,
              letterSpacing: mono ? theme.letterSpacing.wide : undefined,
            },
            inputStyle,
          ]}
          placeholderTextColor={theme.color.textTertiary}
          secureTextEntry={secure && !revealed}
          accessibilityLabel={label}
          accessibilityHint={error ?? hint}
          onFocus={(event) => {
            setFocused(true);
            onFocus?.(event);
          }}
          onBlur={(event) => {
            setFocused(false);
            onBlur?.(event);
          }}
          {...rest}
        />

        {secure ? (
          <Pressable
            onPress={() => setRevealed((current) => !current)}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={revealed ? `Hide ${label}` : `Show ${label}`}
            style={styles.adornment}
          >
            <Text role="monoSmall" tone="secondary">
              {revealed ? 'HIDE' : 'SHOW'}
            </Text>
          </Pressable>
        ) : null}

        {trailing ? <View style={styles.adornment}>{trailing}</View> : null}
      </View>

      {error || hint ? (
        <Text
          role="caption"
          tone={error ? 'critical' : 'tertiary'}
          style={{ marginTop: theme.spacing.xs }}
          accessibilityLiveRegion={error ? 'polite' : 'none'}
        >
          {error ?? hint}
        </Text>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  field: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  input: { flex: 1, paddingVertical: 10 },
  adornment: { flexShrink: 0 },
});
