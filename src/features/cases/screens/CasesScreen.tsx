import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { useFocusEffect, useRouter } from 'expo-router';

import { AppHeader } from '@/components/layout/AppHeader';
import { Section } from '@/components/layout/Panel';
import { Button } from '@/components/primitives/Button';
import { Text } from '@/components/primitives/Text';
import { TextField } from '@/components/primitives/TextField';
import { BottomSheet } from '@/components/overlay/Sheet';
import { EmptyState, ErrorState, LoadingState } from '@/components/feedback/States';
import { DOCUMENT_TYPE_DESCRIPTORS } from '@/constants/documents';
import { ROUTES } from '@/constants/routes';
import { useResponsive } from '@/hooks/useResponsive';
import { useTheme } from '@/theme';
import {
  DOCUMENT_TYPES,
  type CaseStatus,
  type DocumentType,
  type RiskLevel,
  type SyncState,
} from '@/types';

import { CaseRow } from '../components/CaseRow';
import { useCaseSummaries, useRefreshCases } from '../useCases';

type DateWindow = 'ALL' | 'TODAY' | 'WEEK' | 'MONTH';

interface Filters {
  risk: RiskLevel[];
  status: CaseStatus[];
  documentType: DocumentType[];
  sync: SyncState[];
  window: DateWindow;
}

const EMPTY_FILTERS: Filters = {
  risk: [],
  status: [],
  documentType: [],
  sync: [],
  window: 'ALL',
};

const RISK_OPTIONS: RiskLevel[] = ['LOW', 'REVIEW', 'HIGH'];
const STATUS_OPTIONS: CaseStatus[] = [
  'DRAFT',
  'CAPTURING',
  'SCREENING',
  'AWAITING_DECISION',
  'COMPLETED',
  'ABANDONED',
];
const SYNC_OPTIONS: SyncState[] = ['LOCAL_ONLY', 'PENDING', 'SYNCING', 'SYNCED', 'FAILED'];

/**
 * The case list.
 *
 * Filters are held in a sheet rather than on the screen: an officer opening this
 * list is usually looking for one specific case, and search alone answers that.
 * Filtering is the less common path and does not deserve permanent screen space.
 *
 * The list is virtualised because a device at a busy post accumulates thousands
 * of cases over a posting, and every one of them stays on the device until the
 * retention policy removes it.
 */
export function CasesScreen() {
  const router = useRouter();
  const theme = useTheme();
  const { isTablet, contentMaxWidth } = useResponsive();

  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const query = useMemo(
    () => ({
      search: search.trim() || undefined,
      riskLevel: filters.risk.length > 0 ? filters.risk : undefined,
      status: filters.status.length > 0 ? filters.status : undefined,
      documentType: filters.documentType.length > 0 ? filters.documentType : undefined,
      syncState: filters.sync.length > 0 ? filters.sync : undefined,
      createdAfter: windowToIso(filters.window),
      limit: 500,
    }),
    [search, filters],
  );

  const cases = useCaseSummaries(query);
  const refreshCases = useRefreshCases();

  useFocusEffect(
    useCallback(() => {
      refreshCases();
    }, [refreshCases]),
  );

  const activeFilterCount =
    filters.risk.length +
    filters.status.length +
    filters.documentType.length +
    filters.sync.length +
    (filters.window === 'ALL' ? 0 : 1);

  const openCase = useCallback((id: string) => router.push(ROUTES.caseDetail(id)), [router]);

  const data = cases.data ?? [];

  return (
    <>
      <AppHeader
        title="Cases"
        subtitle={
          cases.isLoading
            ? 'Reading local records'
            : `${data.length} ${data.length === 1 ? 'case' : 'cases'}${activeFilterCount > 0 ? ' matching' : ' on this device'}`
        }
        right={
          <Button
            label={activeFilterCount > 0 ? `Filters (${activeFilterCount})` : 'Filters'}
            onPress={() => setFiltersOpen(true)}
            variant="ghost"
            size="medium"
          />
        }
      />

      <View style={[styles.root, { backgroundColor: theme.color.canvas }]}>
        <View
          style={[
            styles.searchBar,
            {
              paddingHorizontal: theme.spacing.lg,
              paddingTop: theme.spacing.md,
              paddingBottom: theme.spacing.sm,
            },
            isTablet ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : null,
          ]}
        >
          <TextField
            label="Search"
            value={search}
            onChangeText={setSearch}
            placeholder="Case reference, or last digits of a document number"
            autoCapitalize="characters"
            autoCorrect={false}
            mono
            returnKeyType="search"
            testID="cases-search"
          />
        </View>

        {cases.isLoading ? (
          <LoadingState label="Reading local records" />
        ) : cases.isError ? (
          <ErrorState
            title="Cases could not be read"
            message="The local case store could not be opened. Restart the application, and report the fault if it repeats."
            actionLabel="Try again"
            onAction={() => void cases.refetch()}
          />
        ) : data.length === 0 ? (
          <EmptyState
            title={
              search || activeFilterCount > 0 ? 'No cases match' : 'No cases on this device yet'
            }
            message={
              search || activeFilterCount > 0
                ? 'Adjust the search or clear the filters to widen the results.'
                : 'Cases appear here as soon as you start screening, whether or not they have been uploaded.'
            }
            actionLabel={search || activeFilterCount > 0 ? 'Clear filters' : 'Start a screening'}
            onAction={() => {
              if (search || activeFilterCount > 0) {
                setSearch('');
                setFilters(EMPTY_FILTERS);
              } else {
                router.push(ROUTES.app.dashboard);
              }
            }}
          />
        ) : (
          <View
            style={[
              styles.listWrapper,
              isTablet ? { maxWidth: contentMaxWidth, alignSelf: 'center', width: '100%' } : null,
            ]}
          >
            <FlashList
              data={data}
              keyExtractor={(item) => item.id}
              renderItem={({ item, index }) => (
                <CaseRow summary={item} onPress={openCase} separated={index > 0} />
              )}
              contentContainerStyle={{
                paddingHorizontal: theme.spacing.lg,
                paddingBottom: theme.spacing.giant,
              }}
              onRefresh={refreshCases}
              refreshing={cases.isFetching}
              showsVerticalScrollIndicator={false}
              testID="cases-list"
            />
          </View>
        )}
      </View>

      <BottomSheet
        visible={filtersOpen}
        onDismiss={() => setFiltersOpen(false)}
        title="Filter cases"
        description="Filters combine: a case must match every group you narrow."
        footer={
          <View style={[styles.sheetFooter, { paddingBottom: theme.spacing.md }]}>
            <Button
              label="Clear all"
              onPress={() => setFilters(EMPTY_FILTERS)}
              variant="secondary"
              style={styles.sheetSecondary}
            />
            <Button
              label="Show results"
              onPress={() => setFiltersOpen(false)}
              style={styles.sheetPrimary}
            />
          </View>
        }
      >
        <Section title="Risk level" style={{ marginTop: 0 }}>
          <ChipGroup
            options={RISK_OPTIONS.map((level) => ({
              value: level,
              label: level.charAt(0) + level.slice(1).toLowerCase(),
            }))}
            selected={filters.risk}
            onToggle={(value) =>
              setFilters((current) => ({ ...current, risk: toggle(current.risk, value) }))
            }
          />
        </Section>

        <Section title="Status">
          <ChipGroup
            options={STATUS_OPTIONS.map((status) => ({
              value: status,
              label: status
                .toLowerCase()
                .replace(/_/g, ' ')
                .replace(/^./, (character) => character.toUpperCase()),
            }))}
            selected={filters.status}
            onToggle={(value) =>
              setFilters((current) => ({ ...current, status: toggle(current.status, value) }))
            }
          />
        </Section>

        <Section title="Document type">
          <ChipGroup
            options={DOCUMENT_TYPES.map((type) => ({
              value: type,
              label: DOCUMENT_TYPE_DESCRIPTORS[type].label,
            }))}
            selected={filters.documentType}
            onToggle={(value) =>
              setFilters((current) => ({
                ...current,
                documentType: toggle(current.documentType, value),
              }))
            }
          />
        </Section>

        <Section title="Synchronisation">
          <ChipGroup
            options={SYNC_OPTIONS.map((state) => ({
              value: state,
              label: state
                .toLowerCase()
                .replace(/_/g, ' ')
                .replace(/^./, (character) => character.toUpperCase()),
            }))}
            selected={filters.sync}
            onToggle={(value) =>
              setFilters((current) => ({ ...current, sync: toggle(current.sync, value) }))
            }
          />
        </Section>

        <Section title="Created" style={{ marginBottom: theme.spacing.xl }}>
          <ChipGroup
            options={[
              { value: 'ALL' as DateWindow, label: 'Any time' },
              { value: 'TODAY' as DateWindow, label: 'Today' },
              { value: 'WEEK' as DateWindow, label: 'Last 7 days' },
              { value: 'MONTH' as DateWindow, label: 'Last 30 days' },
            ]}
            selected={[filters.window]}
            onToggle={(value) => setFilters((current) => ({ ...current, window: value }))}
          />
        </Section>
      </BottomSheet>
    </>
  );
}

function ChipGroup<T extends string>({
  options,
  selected,
  onToggle,
}: {
  options: { value: T; label: string }[];
  selected: readonly T[];
  onToggle: (value: T) => void;
}) {
  const theme = useTheme();
  return (
    <View style={styles.chipGroup}>
      {options.map((option) => {
        const isSelected = selected.includes(option.value);
        return (
          <Pressable
            key={option.value}
            onPress={() => onToggle(option.value)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: isSelected }}
            accessibilityLabel={option.label}
            style={({ pressed }) => [
              styles.chip,
              {
                borderRadius: theme.radii.sm,
                borderWidth: theme.borderWidth.thin,
                borderColor: isSelected ? theme.color.accent : theme.color.border,
                backgroundColor: isSelected
                  ? theme.color.accentSubtle
                  : pressed
                    ? theme.color.surfaceSunken
                    : 'transparent',
                paddingHorizontal: theme.spacing.md,
                paddingVertical: theme.spacing.sm,
              },
            ]}
          >
            <Text
              role="caption"
              weight={isSelected ? 'semibold' : 'regular'}
              tone={isSelected ? 'accent' : 'secondary'}
              accessible={false}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function toggle<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((entry) => entry !== value) : [...list, value];
}

function windowToIso(window: DateWindow): string | undefined {
  if (window === 'ALL') return undefined;
  const now = new Date();
  if (window === 'TODAY') {
    now.setHours(0, 0, 0, 0);
    return now.toISOString();
  }
  const days = window === 'WEEK' ? 7 : 30;
  return new Date(now.getTime() - days * 86_400_000).toISOString();
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  searchBar: {},
  listWrapper: { flex: 1 },
  chipGroup: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {},
  sheetFooter: { flexDirection: 'row', gap: 8 },
  sheetSecondary: { flexShrink: 0 },
  sheetPrimary: { flex: 1 },
});
