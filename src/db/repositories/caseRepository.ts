import { hasEvidence, type DocumentType, type RiskLevel, type ScreeningCaseResult } from '@/contracts';
import type {
  CaseId,
  CaseStatus,
  CaseSummary,
  OfficerDecision,
  OfficerDecisionType,
  ScreeningCase,
  ScreeningStageState,
  SyncState,
} from '@/types';
import { nowIso } from '@/utils/date';
import { formatCaseReference, newId } from '@/utils/id';
import { maskDocumentNumber } from '@/utils/mask';

import { getDatabase, parsePayload, toDbBool } from '../client';
import type { CaseRow, CountRow, DecisionRow, DocumentRow } from '../rows';

/** Filters applied by the cases list. Every field is optional. */
export interface CaseQuery {
  status?: readonly CaseStatus[];
  riskLevel?: readonly RiskLevel[];
  documentType?: readonly DocumentType[];
  syncState?: readonly SyncState[];
  /** Inclusive lower bound on `created_at`. */
  createdAfter?: string;
  /** Matches the case reference or the masked document number. */
  search?: string;
  limit?: number;
  offset?: number;
}

export interface CaseCounts {
  total: number;
  active: number;
  awaitingDecision: number;
  pendingSync: number;
  highRisk: number;
  completedToday: number;
}

/**
 * The only module permitted to speak SQL about cases.
 *
 * The screening result is stored exactly as the service returned it, in one
 * row. The repository does not decompose it, re-interpret it, or recompute
 * anything from it — the few facts the case list needs are denormalised onto
 * `cases` purely so a list query does not have to parse a document per row.
 */
export interface CaseRepository {
  save(screeningCase: ScreeningCase): Promise<void>;
  findById(id: CaseId): Promise<ScreeningCase | null>;
  listSummaries(query?: CaseQuery): Promise<CaseSummary[]>;
  counts(): Promise<CaseCounts>;
  remove(id: CaseId): Promise<void>;
  /** Allocates the next per-year case reference, e.g. `SSB-2026-0042`. */
  nextReference(year: number): Promise<string>;
  updateSync(id: CaseId, state: SyncState, error?: string | null): Promise<void>;
  findDecision(id: CaseId): Promise<OfficerDecision | null>;
}

interface CaseResultRow {
  case_id: string;
  schema_version: string;
  payload: string;
  generated_at: string;
}

function toSummary(row: CaseRow): CaseSummary {
  return {
    id: row.id,
    status: row.status as CaseStatus,
    documentType: row.document_type as DocumentType,
    maskedDocumentNumber: row.masked_document_number,
    subjectName: row.subject_name,
    riskLevel: row.risk_level as RiskLevel | null,
    riskScore: row.risk_score,
    decision: row.decision as OfficerDecisionType | null,
    syncState: row.sync_state as SyncState,
    officerName: row.officer_name,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function toDecision(row: DecisionRow): OfficerDecision {
  return {
    id: row.id,
    caseId: row.case_id,
    decision: row.decision as OfficerDecisionType,
    remarks: row.remarks,
    officerId: row.officer_id,
    officerName: row.officer_name,
    decidedAt: row.decided_at,
    // Stored empty when the screening produced no risk result, so a case
    // decided without an assessment is not given one after the fact.
    riskLevelAtDecision: (row.risk_level_at_decision || null) as RiskLevel | null,
    riskScoreAtDecision: row.risk_score_at_decision,
    divergedFromRecommendation: row.diverged === 1,
  };
}

/**
 * Reads the two identifying facts the case list shows.
 *
 * Both come from the OCR module's own output; neither is inferred. The document
 * number is masked before it is written, so the list index never holds a
 * complete one.
 */
function deriveListFields(result: ScreeningCaseResult | null): {
  subjectName: string | null;
  maskedDocumentNumber: string | null;
} {
  if (!result || !hasEvidence(result.ocr)) {
    return { subjectName: null, maskedDocumentNumber: null };
  }
  const fields = result.ocr.result.fields;
  const value = (key: string) => fields.find((field) => field.key === key)?.value ?? null;

  const surname = value('surname') ?? '';
  const given = value('given_names') ?? '';
  const combined = `${given} ${surname}`.trim();

  const documentNumber =
    value('passport_number') ?? value('document_number') ?? value('id_number') ??
    value('license_number');

  return {
    subjectName: combined.length > 0 ? combined : null,
    maskedDocumentNumber: maskDocumentNumber(documentNumber),
  };
}

class SqliteCaseRepository implements CaseRepository {
  async save(screeningCase: ScreeningCase): Promise<void> {
    const db = await getDatabase();
    const c = screeningCase;
    const risk = c.result && hasEvidence(c.result.risk) ? c.result.risk.result : null;
    const { subjectName, maskedDocumentNumber } = deriveListFields(c.result);
    const savedAt = nowIso();

    await db.withTransactionAsync(async () => {
      await db.runAsync(
        `INSERT INTO cases (
           id, status, document_type, subject_name, masked_document_number,
           risk_level, risk_score, decision, sync_state, sync_attempts,
           sync_last_attempt_at, sync_last_synced_at, sync_last_error,
           officer_id, officer_name, unit, post_name, scenario_id,
           stages_payload, created_at, updated_at
         ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
         ON CONFLICT(id) DO UPDATE SET
           status = excluded.status,
           document_type = excluded.document_type,
           subject_name = excluded.subject_name,
           masked_document_number = excluded.masked_document_number,
           risk_level = excluded.risk_level,
           risk_score = excluded.risk_score,
           decision = excluded.decision,
           sync_state = excluded.sync_state,
           sync_attempts = excluded.sync_attempts,
           sync_last_attempt_at = excluded.sync_last_attempt_at,
           sync_last_synced_at = excluded.sync_last_synced_at,
           sync_last_error = excluded.sync_last_error,
           stages_payload = excluded.stages_payload,
           updated_at = excluded.updated_at`,
        [
          c.id,
          c.status,
          c.documentType,
          subjectName,
          maskedDocumentNumber,
          risk?.risk_level ?? null,
          risk?.risk_score ?? null,
          c.decision?.decision ?? null,
          c.sync.state,
          c.sync.attempts,
          c.sync.lastAttemptAt,
          c.sync.lastSyncedAt,
          c.sync.lastError,
          c.officerId,
          c.officerName,
          c.unit,
          c.postName,
          null,
          JSON.stringify(c.stages),
          c.createdAt,
          savedAt,
        ],
      );

      await db.runAsync('DELETE FROM documents WHERE case_id = ?', [c.id]);
      for (const [kind, record] of [
        ['DOCUMENT', c.document],
        ['PERSON', c.person],
      ] as const) {
        if (!record) continue;
        await db.runAsync(
          `INSERT INTO documents (
             id, case_id, kind, declared_type, image_uri, image_width, image_height,
             image_bytes, capture_source, captured_at, analysis_payload
           ) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)`,
          [
            record.id,
            c.id,
            kind,
            'declaredType' in record ? record.declaredType : null,
            record.image.uri,
            record.image.width,
            record.image.height,
            record.image.sizeBytes,
            record.image.source,
            record.image.capturedAt,
          ],
        );
      }

      if (c.result) {
        // Stored verbatim. The application is a consumer of this document, not
        // its author, and re-serialising a reshaped copy would make the stored
        // record something the service never actually said.
        await db.runAsync(
          `INSERT INTO case_results (case_id, schema_version, payload, generated_at)
           VALUES (?,?,?,?)
           ON CONFLICT(case_id) DO UPDATE SET
             schema_version = excluded.schema_version,
             payload = excluded.payload,
             generated_at = excluded.generated_at`,
          [c.id, c.result.schema_version, JSON.stringify(c.result), c.result.generated_at],
        );
      }

      if (c.decision) {
        await db.runAsync(
          `INSERT INTO officer_decisions (
             id, case_id, decision, remarks, officer_id, officer_name, decided_at,
             risk_level_at_decision, risk_score_at_decision, diverged
           ) VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             decision = excluded.decision,
             remarks = excluded.remarks,
             decided_at = excluded.decided_at`,
          [
            c.decision.id,
            c.id,
            c.decision.decision,
            c.decision.remarks,
            c.decision.officerId,
            c.decision.officerName,
            c.decision.decidedAt,
            c.decision.riskLevelAtDecision ?? '',
            c.decision.riskScoreAtDecision ?? 0,
            toDbBool(c.decision.divergedFromRecommendation),
          ],
        );
      }
    });
  }

  async findById(id: CaseId): Promise<ScreeningCase | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<CaseRow>('SELECT * FROM cases WHERE id = ?', [id]);
    if (!row) return null;

    const [documents, resultRow, decisionRow] = await Promise.all([
      db.getAllAsync<DocumentRow>('SELECT * FROM documents WHERE case_id = ?', [id]),
      db.getFirstAsync<CaseResultRow>('SELECT * FROM case_results WHERE case_id = ?', [id]),
      db.getFirstAsync<DecisionRow>(
        'SELECT * FROM officer_decisions WHERE case_id = ? ORDER BY decided_at DESC LIMIT 1',
        [id],
      ),
    ]);

    const documentRow = documents.find((entry) => entry.kind === 'DOCUMENT') ?? null;
    const personRow = documents.find((entry) => entry.kind === 'PERSON') ?? null;

    return {
      id: row.id,
      status: row.status as CaseStatus,
      documentType: row.document_type as DocumentType,
      document: documentRow
        ? {
            id: documentRow.id,
            caseId: row.id,
            declaredType: (documentRow.declared_type ?? row.document_type) as DocumentType,
            image: {
              uri: documentRow.image_uri,
              width: documentRow.image_width,
              height: documentRow.image_height,
              sizeBytes: documentRow.image_bytes,
              source: documentRow.capture_source as 'CAMERA' | 'IMPORTED',
              capturedAt: documentRow.captured_at,
            },
          }
        : null,
      person: personRow
        ? {
            id: personRow.id,
            caseId: row.id,
            image: {
              uri: personRow.image_uri,
              width: personRow.image_width,
              height: personRow.image_height,
              sizeBytes: personRow.image_bytes,
              source: personRow.capture_source as 'CAMERA' | 'IMPORTED',
              capturedAt: personRow.captured_at,
            },
          }
        : null,
      stages: parsePayload<ScreeningStageState[]>(row.stages_payload) ?? [],
      result: parsePayload<ScreeningCaseResult>(resultRow?.payload),
      decision: decisionRow ? toDecision(decisionRow) : null,
      sync: {
        state: row.sync_state as SyncState,
        attempts: row.sync_attempts,
        lastAttemptAt: row.sync_last_attempt_at,
        lastSyncedAt: row.sync_last_synced_at,
        lastError: row.sync_last_error,
      },
      officerId: row.officer_id,
      officerName: row.officer_name,
      unit: row.unit,
      postName: row.post_name,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    };
  }

  async listSummaries(query: CaseQuery = {}): Promise<CaseSummary[]> {
    const db = await getDatabase();
    const clauses: string[] = [];
    const params: (string | number)[] = [];

    if (query.status?.length) {
      clauses.push(`status IN (${query.status.map(() => '?').join(',')})`);
      params.push(...query.status);
    }
    if (query.riskLevel?.length) {
      clauses.push(`risk_level IN (${query.riskLevel.map(() => '?').join(',')})`);
      params.push(...query.riskLevel);
    }
    if (query.documentType?.length) {
      clauses.push(`document_type IN (${query.documentType.map(() => '?').join(',')})`);
      params.push(...query.documentType);
    }
    if (query.syncState?.length) {
      clauses.push(`sync_state IN (${query.syncState.map(() => '?').join(',')})`);
      params.push(...query.syncState);
    }
    if (query.createdAfter) {
      clauses.push('created_at >= ?');
      params.push(query.createdAfter);
    }
    if (query.search?.trim()) {
      // Officers search by case reference or by the last digits of a document
      // number; the full number is never stored in this column.
      const term = `%${query.search.trim().toUpperCase()}%`;
      clauses.push("(UPPER(id) LIKE ? OR UPPER(COALESCE(masked_document_number, '')) LIKE ?)");
      params.push(term, term);
    }

    const where = clauses.length > 0 ? `WHERE ${clauses.join(' AND ')}` : '';
    const rows = await db.getAllAsync<CaseRow>(
      `SELECT * FROM cases ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`,
      [...params, query.limit ?? 200, query.offset ?? 0],
    );
    return rows.map(toSummary);
  }

  async counts(): Promise<CaseCounts> {
    const db = await getDatabase();
    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    const since = startOfDay.toISOString();

    const [total, active, awaiting, pending, highRisk, today] = await Promise.all([
      db.getFirstAsync<CountRow>('SELECT COUNT(*) AS count FROM cases'),
      db.getFirstAsync<CountRow>(
        "SELECT COUNT(*) AS count FROM cases WHERE status IN ('DRAFT','CAPTURING','SCREENING')",
      ),
      db.getFirstAsync<CountRow>(
        "SELECT COUNT(*) AS count FROM cases WHERE status = 'AWAITING_DECISION'",
      ),
      db.getFirstAsync<CountRow>(
        "SELECT COUNT(*) AS count FROM cases WHERE sync_state IN ('PENDING','FAILED')",
      ),
      db.getFirstAsync<CountRow>("SELECT COUNT(*) AS count FROM cases WHERE risk_level = 'HIGH'"),
      db.getFirstAsync<CountRow>(
        "SELECT COUNT(*) AS count FROM cases WHERE status = 'COMPLETED' AND updated_at >= ?",
        [since],
      ),
    ]);

    return {
      total: total?.count ?? 0,
      active: active?.count ?? 0,
      awaitingDecision: awaiting?.count ?? 0,
      pendingSync: pending?.count ?? 0,
      highRisk: highRisk?.count ?? 0,
      completedToday: today?.count ?? 0,
    };
  }

  async remove(id: CaseId): Promise<void> {
    const db = await getDatabase();
    await db.runAsync('DELETE FROM cases WHERE id = ?', [id]);
  }

  async nextReference(year: number): Promise<string> {
    const db = await getDatabase();
    let sequence = 1;
    await db.withTransactionAsync(async () => {
      const row = await db.getFirstAsync<{ last_seq: number }>(
        'SELECT last_seq FROM case_sequence WHERE year = ?',
        [year],
      );
      sequence = (row?.last_seq ?? 0) + 1;
      await db.runAsync(
        `INSERT INTO case_sequence (year, last_seq) VALUES (?, ?)
         ON CONFLICT(year) DO UPDATE SET last_seq = excluded.last_seq`,
        [year, sequence],
      );
    });
    return formatCaseReference(year, sequence);
  }

  async updateSync(id: CaseId, state: SyncState, error: string | null = null): Promise<void> {
    const db = await getDatabase();
    const timestamp = nowIso();
    await db.runAsync(
      `UPDATE cases SET
         sync_state = ?,
         sync_last_attempt_at = ?,
         sync_last_synced_at = CASE WHEN ? = 'SYNCED' THEN ? ELSE sync_last_synced_at END,
         sync_last_error = ?,
         sync_attempts = CASE WHEN ? = 'FAILED' THEN sync_attempts + 1 ELSE sync_attempts END
       WHERE id = ?`,
      [state, timestamp, state, timestamp, error, state, id],
    );
  }

  async findDecision(id: CaseId): Promise<OfficerDecision | null> {
    const db = await getDatabase();
    const row = await db.getFirstAsync<DecisionRow>(
      'SELECT * FROM officer_decisions WHERE case_id = ? ORDER BY decided_at DESC LIMIT 1',
      [id],
    );
    return row ? toDecision(row) : null;
  }
}

/** Builds a decision record ready to persist. */
export function createDecisionRecord(input: Omit<OfficerDecision, 'id'>): OfficerDecision {
  return { id: newId(), ...input };
}

export const caseRepository: CaseRepository = new SqliteCaseRepository();
