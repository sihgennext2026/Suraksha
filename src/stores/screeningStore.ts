import { create } from 'zustand';

import { hasEvidence, type DocumentType } from '@/contracts';
import { STORAGE_KEYS } from '@/constants/storage';
import { MODULE_LABELS } from '@/constants/screening';
import { auditRepository, caseRepository } from '@/db';
import { getScreeningService } from '@/services/ai/registry';
import type { StageEvent } from '@/services/ai/contracts';
import { keyValueStore, mediaStore } from '@/services/storage';
import { syncEngine } from '@/services/sync/syncEngine';
import {
  SCREENING_STAGE_ORDER,
  type AuthenticatedUser,
  type CapturedImage,
  type OfficerDecisionType,
  type ScreeningCase,
  type ScreeningStageId,
  type ScreeningStageState,
} from '@/types';
import { nowIso } from '@/utils/date';
import { isAbortError, toServiceFailure } from '@/utils/errors';
import { newId } from '@/utils/id';
import { createLogger } from '@/utils/logger';

const log = createLogger('screening');

/** Which step of the workflow the officer has reached. */
export type ScreeningPhase =
  | 'IDLE'
  | 'DOCUMENT_TYPE'
  | 'DOCUMENT_CAPTURE'
  | 'DOCUMENT_REVIEW'
  | 'PERSON_CAPTURE'
  | 'SCREENING'
  | 'RESULT'
  | 'DECISION'
  | 'SAVED';

interface ScreeningState {
  activeCase: ScreeningCase | null;
  phase: ScreeningPhase;
  running: boolean;
  /** Officer-facing text when the screening call itself failed. */
  error: string | null;
  restored: boolean;
  saving: boolean;
  saveError: string | null;

  restore(): Promise<void>;
  start(user: AuthenticatedUser): Promise<ScreeningCase>;
  setDocumentType(type: DocumentType): Promise<void>;
  attachDocument(image: CapturedImage): Promise<void>;
  attachPerson(image: CapturedImage): Promise<void>;
  runScreening(options?: { scenario?: string }): Promise<void>;
  cancelScreening(): void;
  recordDecision(decision: OfficerDecisionType, remarks: string): Promise<void>;
  save(options: { autoSync: boolean; online: boolean }): Promise<string | null>;
  abandon(): Promise<void>;
  clear(): void;
}

let screeningController: AbortController | null = null;

export function createInitialStages(): ScreeningStageState[] {
  return SCREENING_STAGE_ORDER.map((id) => ({
    id,
    status: 'WAITING' as const,
    progress: 0,
    detail: null,
    startedAt: null,
    completedAt: null,
    error: null,
  }));
}

/**
 * The active screening.
 *
 * The store sequences the officer's workflow and persists it. It does not
 * interpret findings: the screening service returns one canonical case document
 * and the store records it unchanged. Nothing here decides what a similarity
 * means, whether a rule failure matters, or how a missing module affects the
 * assessment — all of that is service policy, and keeping it out of the app is
 * the point of this layer.
 *
 * The case row is written the moment a case is opened, not when it finishes, so
 * an interruption loses no capture and every audit event can reference a real
 * case from the first moment.
 */
export const useScreeningStore = create<ScreeningState>((set, get) => {
  function snapshotPhase(caseId: string | null, phase: ScreeningPhase): void {
    if (!caseId) {
      void keyValueStore.remove(STORAGE_KEYS.activeScreening);
      return;
    }
    void keyValueStore.setJson(STORAGE_KEYS.activeScreening, { caseId, phase });
  }

  async function commit(
    mutate: (current: ScreeningCase) => ScreeningCase,
    phase?: ScreeningPhase,
  ): Promise<ScreeningCase | null> {
    const current = get().activeCase;
    if (!current) return null;

    const next = { ...mutate(current), updatedAt: nowIso() };
    const nextPhase = phase ?? get().phase;
    set({ activeCase: next, phase: nextPhase });
    snapshotPhase(next.id, nextPhase);

    try {
      await caseRepository.save(next);
    } catch (error) {
      // Losing a write is recoverable; losing the subject at the counter is not.
      log.warn('Could not write the case through to storage', { caseId: next.id, ok: false });
      void error;
    }
    return next;
  }

  return {
    activeCase: null,
    phase: 'IDLE',
    running: false,
    error: null,
    restored: false,
    saving: false,
    saveError: null,

    async restore() {
      const stored = await keyValueStore.getJson<{ caseId: string; phase: ScreeningPhase }>(
        STORAGE_KEYS.activeScreening,
      );
      if (!stored?.caseId) {
        set({ restored: true });
        return;
      }

      const recovered = await caseRepository.findById(stored.caseId);
      if (!recovered || recovered.status === 'COMPLETED' || recovered.status === 'ABANDONED') {
        snapshotPhase(null, 'IDLE');
        set({ restored: true });
        return;
      }

      // A run interrupted mid-screening cannot resume where it stopped, so the
      // officer is returned to the point where it can be re-run from the
      // captures they already took — seconds, rather than another handover.
      const wasScreening = stored.phase === 'SCREENING';
      set({
        activeCase: wasScreening
          ? { ...recovered, stages: createInitialStages(), status: 'CAPTURING' }
          : recovered,
        phase: wasScreening ? 'PERSON_CAPTURE' : stored.phase,
        restored: true,
        running: false,
        error: null,
      });
      log.info('Recovered an interrupted screening', { phase: stored.phase });
    },

    async start(user) {
      const year = new Date().getFullYear();
      const reference = await caseRepository.nextReference(year);
      const created: ScreeningCase = {
        id: reference,
        status: 'DRAFT',
        documentType: 'passport',
        document: null,
        person: null,
        stages: createInitialStages(),
        result: null,
        decision: null,
        sync: {
          state: 'LOCAL_ONLY',
          lastAttemptAt: null,
          lastSyncedAt: null,
          attempts: 0,
          lastError: null,
        },
        officerId: user.officerId,
        officerName: user.name,
        unit: user.unit,
        postName: user.postName,
        createdAt: nowIso(),
        updatedAt: nowIso(),
      };

      set({
        activeCase: created,
        phase: 'DOCUMENT_TYPE',
        error: null,
        saveError: null,
        running: false,
      });
      snapshotPhase(created.id, 'DOCUMENT_TYPE');

      await caseRepository.save(created);
      await auditRepository.record({
        caseId: created.id,
        type: 'CASE_CREATED',
        description: `Case ${reference} opened`,
        actorId: user.officerId,
        actorName: user.name,
        metadata: { post: user.postName },
      });
      return created;
    },

    async setDocumentType(type) {
      const next = await commit(
        (current) => ({ ...current, documentType: type }),
        'DOCUMENT_CAPTURE',
      );
      if (!next) return;
      await auditRepository.record({
        caseId: next.id,
        type: 'DOCUMENT_TYPE_SELECTED',
        description: `Document type set to ${type.replace(/_/g, ' ')} by the officer`,
        actorId: next.officerId,
        actorName: next.officerName,
        metadata: { documentType: type },
      });
    },

    async attachDocument(image) {
      const current = get().activeCase;
      if (!current) return;

      const persisted = await mediaStore.persistCapture(current.id, 'document', image);
      const next = await commit(
        (activeCase) => ({
          ...activeCase,
          status: 'CAPTURING',
          document: {
            id: activeCase.document?.id ?? newId(),
            caseId: activeCase.id,
            declaredType: activeCase.documentType,
            image: persisted,
          },
        }),
        'DOCUMENT_REVIEW',
      );
      if (!next) return;

      await auditRepository.record({
        caseId: next.id,
        type: 'DOCUMENT_CAPTURED',
        description: `Document captured from ${
          persisted.source === 'CAMERA' ? 'the camera' : 'an imported image'
        }`,
        actorId: next.officerId,
        actorName: next.officerName,
        metadata: { source: persisted.source },
      });
    },

    async attachPerson(image) {
      const current = get().activeCase;
      if (!current) return;

      const persisted = await mediaStore.persistCapture(current.id, 'person', image);
      const next = await commit(
        (activeCase) => ({
          ...activeCase,
          person: {
            id: activeCase.person?.id ?? newId(),
            caseId: activeCase.id,
            image: persisted,
          },
        }),
        'SCREENING',
      );
      if (!next) return;

      await auditRepository.record({
        caseId: next.id,
        type: 'PERSON_CAPTURED',
        description: 'Subject photograph captured',
        actorId: next.officerId,
        actorName: next.officerName,
        metadata: { source: persisted.source },
      });
    },

    async runScreening(options = {}) {
      const current = get().activeCase;
      if (!current?.document || !current.person) return;
      if (get().running) return;

      screeningController?.abort();
      screeningController = new AbortController();

      set({
        running: true,
        error: null,
        activeCase: { ...current, status: 'SCREENING', stages: createInitialStages() },
        phase: 'SCREENING',
      });
      snapshotPhase(current.id, 'SCREENING');

      await auditRepository.record({
        caseId: current.id,
        type: 'SCREENING_STARTED',
        description: 'Screening started',
        actorId: current.officerId,
        actorName: current.officerName,
        metadata: { documentType: current.documentType },
      });

      const service = getScreeningService({ scenario: options.scenario });

      try {
        const result = await service.screen({
          caseId: current.id,
          documentType: current.documentType,
          documentImage: current.document.image,
          personImage: current.person.image,
          signal: screeningController.signal,
          onStage: (event) => applyStageEvent(set, get, event),
        });

        const settled: ScreeningCase = {
          ...(get().activeCase ?? current),
          result,
          status: 'AWAITING_DECISION',
          updatedAt: nowIso(),
        };

        set({ activeCase: settled, running: false, error: null, phase: 'RESULT' });
        snapshotPhase(settled.id, 'RESULT');

        try {
          await caseRepository.save(settled);
        } catch (error) {
          log.warn('Could not persist screening results', { caseId: settled.id, ok: false });
          void error;
        }
        await recordModuleAudit(settled);
      } catch (error) {
        if (isAbortError(error)) {
          set({ running: false });
          return;
        }
        const failure = toServiceFailure(error);
        set({ running: false, error: failure.message, phase: 'SCREENING' });
        await auditRepository.record({
          caseId: current.id,
          type: 'SCREENING_FAILED',
          description: 'The screening service could not be reached',
          actorId: current.officerId,
          actorName: current.officerName,
          metadata: { code: failure.code },
        });
      }
    },

    cancelScreening() {
      screeningController?.abort();
      screeningController = null;
      set({ running: false });
    },

    async recordDecision(decision, remarks) {
      const current = get().activeCase;
      if (!current) return;

      const risk =
        current.result && hasEvidence(current.result.risk) ? current.result.risk.result : null;

      const next = await commit(
        (activeCase) => ({
          ...activeCase,
          status: 'COMPLETED',
          decision: {
            id: activeCase.decision?.id ?? newId(),
            caseId: activeCase.id,
            decision,
            remarks: remarks.trim(),
            officerId: activeCase.officerId,
            officerName: activeCase.officerName,
            decidedAt: nowIso(),
            // Null when no assessment was produced: a case decided without one
            // must not be given a risk level after the fact.
            riskLevelAtDecision: risk?.risk_level ?? null,
            riskScoreAtDecision: risk?.risk_score ?? null,
            divergedFromRecommendation: risk
              ? recommendationFor(risk.risk_level) !== decision
              : false,
          },
        }),
        'DECISION',
      );
      if (!next?.decision) return;

      await auditRepository.record({
        caseId: next.id,
        type: 'OFFICER_DECISION',
        description: `Officer recorded the decision: ${decisionDescription(decision)}`,
        actorId: next.officerId,
        actorName: next.officerName,
        metadata: {
          decision,
          riskLevel: next.decision.riskLevelAtDecision ?? 'NONE',
          riskScore: next.decision.riskScoreAtDecision ?? -1,
          divergedFromRecommendation: next.decision.divergedFromRecommendation,
          hasRemarks: next.decision.remarks.length > 0,
        },
      });
    },

    async save({ autoSync, online }) {
      const current = get().activeCase;
      if (!current || get().saving) return null;

      set({ saving: true, saveError: null });
      try {
        await caseRepository.save(current);
        await auditRepository.record({
          caseId: current.id,
          type: 'CASE_SAVED',
          description: 'Case committed to this device',
          actorId: current.officerId,
          actorName: current.officerName,
          metadata: {
            riskLevel:
              current.result && hasEvidence(current.result.risk)
                ? current.result.risk.result.risk_level
                : 'NONE',
          },
        });

        await syncEngine.enqueue(current.id);
        if (autoSync && online) {
          // Not awaited: the officer's next subject should not wait on an
          // upload. Failures land in the queue and surface on the dashboard.
          void syncEngine.run({
            online,
            actorId: current.officerId,
            actorName: current.officerName,
          });
        }

        set({ phase: 'SAVED', saving: false });
        snapshotPhase(null, 'IDLE');
        return current.id;
      } catch (error) {
        log.error('Could not save the case locally');
        void error;
        set({
          saving: false,
          saveError:
            'Unable to save this case on the device. Check available storage and try ' +
            'again — the screening is still in memory.',
        });
        return null;
      }
    },

    async abandon() {
      const current = get().activeCase;
      screeningController?.abort();
      screeningController = null;

      if (current) {
        // Marked abandoned rather than deleted: the audit trail is evidence
        // that a screening was started, and deleting the row would cascade it
        // away.
        await caseRepository.save({ ...current, status: 'ABANDONED', updatedAt: nowIso() });
        await auditRepository.record({
          caseId: current.id,
          type: 'CASE_ABANDONED',
          description: `Case ${current.id} abandoned before a decision was recorded`,
          actorId: current.officerId,
          actorName: current.officerName,
          metadata: { phase: get().phase },
        });
        await mediaStore.removeCaseMedia(current.id);
      }

      set({ activeCase: null, phase: 'IDLE', running: false, error: null, saveError: null });
      snapshotPhase(null, 'IDLE');
    },

    clear() {
      screeningController?.abort();
      screeningController = null;
      set({ activeCase: null, phase: 'IDLE', running: false, error: null, saveError: null });
      snapshotPhase(null, 'IDLE');
    },
  };
});

/** Folds a stage event from the service into the progress list. */
function applyStageEvent(
  set: (partial: Partial<ScreeningState>) => void,
  get: () => ScreeningState,
  event: StageEvent,
): void {
  const active = get().activeCase;
  if (!active) return;

  set({
    activeCase: {
      ...active,
      stages: active.stages.map((stage) =>
        stage.id === event.stage
          ? {
              ...stage,
              status: event.status,
              progress: event.progress,
              detail: event.detail,
              error: event.error,
              startedAt:
                event.status === 'PROCESSING' && !stage.startedAt ? nowIso() : stage.startedAt,
              completedAt: event.status === 'PROCESSING' ? null : nowIso(),
            }
          : stage,
      ),
    },
  });
}

/**
 * Records what each module reported.
 *
 * A module that did not run gets its own event, so the audit trail shows the
 * gap rather than simply omitting the module — an officer reviewing the case
 * later can see that a check was absent, not just that it said nothing.
 */
async function recordModuleAudit(screeningCase: ScreeningCase): Promise<void> {
  const result = screeningCase.result;
  if (!result) return;

  const actor = { actorId: screeningCase.officerId, actorName: screeningCase.officerName };
  const caseId = screeningCase.id;

  const entries: { module: keyof typeof MODULE_LABELS; type: Parameters<
    typeof auditRepository.record
  >[0]['type'] }[] = [
    { module: 'ocr', type: 'OCR_COMPLETED' },
    { module: 'validation', type: 'VALIDATION_COMPLETED' },
    { module: 'face_verification', type: 'FACE_VERIFIED' },
    { module: 'document_forensics', type: 'FORENSICS_COMPLETED' },
    { module: 'anomaly', type: 'ANOMALY_COMPLETED' },
    { module: 'risk', type: 'RISK_GENERATED' },
  ];

  for (const entry of entries) {
    const envelope = result[entry.module];
    const item = result.evidence.find((row) => row.module === entry.module);
    const label = MODULE_LABELS[entry.module];

    if (envelope.status === 'NOT_AVAILABLE' || envelope.status === 'FAILED') {
      await auditRepository.record({
        caseId,
        type: 'MODULE_UNAVAILABLE',
        description: `${label} did not run: ${envelope.errors[0]?.message ?? 'no reason given'}`,
        ...actor,
        metadata: { module: entry.module, status: envelope.status },
      });
      continue;
    }

    await auditRepository.record({
      caseId,
      type: entry.type,
      description: `${label}: ${item?.detail ?? 'completed'}`,
      ...actor,
      metadata: {
        module: entry.module,
        status: envelope.status,
        modelVersion: envelope.model_version,
      },
    });
  }
}

/**
 * Maps a risk band onto the decision it corresponds to, for the sole purpose of
 * recording whether the officer diverged. It is never used to pre-select or
 * suggest a decision.
 */
function recommendationFor(level: 'LOW' | 'REVIEW' | 'HIGH'): OfficerDecisionType {
  return { LOW: 'CLEAR', REVIEW: 'HOLD', HIGH: 'ESCALATE' }[level] as OfficerDecisionType;
}

function decisionDescription(decision: OfficerDecisionType): string {
  return { CLEAR: 'cleared', HOLD: 'held for review', ESCALATE: 'escalated' }[decision];
}

export const selectActiveCase = (state: ScreeningState) => state.activeCase;
export const selectPhase = (state: ScreeningState) => state.phase;
export const selectStages = (state: ScreeningState) => state.activeCase?.stages ?? [];
export const selectResult = (state: ScreeningState) => state.activeCase?.result ?? null;
export const selectIsRunning = (state: ScreeningState) => state.running;
export const selectScreeningError = (state: ScreeningState) => state.error;

export type { ScreeningStageId };
