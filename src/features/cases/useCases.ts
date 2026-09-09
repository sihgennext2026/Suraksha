import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { auditRepository, caseRepository, type CaseQuery } from '@/db';
import type { CaseId } from '@/types';

/**
 * Query keys.
 *
 * Grouped under one root so a single invalidation after a case is saved
 * refreshes the list, the counts, and any open detail without each call site
 * having to remember every dependent key.
 */
export const caseKeys = {
  root: ['cases'] as const,
  list: (query: CaseQuery) => ['cases', 'list', query] as const,
  counts: () => ['cases', 'counts'] as const,
  detail: (id: CaseId) => ['cases', 'detail', id] as const,
  audit: (id: CaseId) => ['cases', 'audit', id] as const,
};

export function useCaseSummaries(query: CaseQuery = {}) {
  return useQuery({
    queryKey: caseKeys.list(query),
    queryFn: () => caseRepository.listSummaries(query),
  });
}

export function useCaseCounts() {
  return useQuery({
    queryKey: caseKeys.counts(),
    queryFn: () => caseRepository.counts(),
  });
}

export function useCaseDetail(id: CaseId | undefined) {
  return useQuery({
    queryKey: caseKeys.detail(id ?? ''),
    queryFn: () => caseRepository.findById(id as CaseId),
    enabled: Boolean(id),
  });
}

export function useCaseAudit(id: CaseId | undefined) {
  return useQuery({
    queryKey: caseKeys.audit(id ?? ''),
    queryFn: () => auditRepository.listForCase(id as CaseId),
    enabled: Boolean(id),
  });
}

/** Invalidates everything derived from the case store. */
export function useRefreshCases() {
  const queryClient = useQueryClient();
  return useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: caseKeys.root });
    void queryClient.invalidateQueries({ queryKey: ['system-status'] });
  }, [queryClient]);
}
