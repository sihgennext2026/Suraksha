/** Raw SQLite row shapes. Repositories are the only place these are visible. */

export interface CaseRow {
  id: string;
  status: string;
  document_type: string;
  subject_name: string | null;
  masked_document_number: string | null;
  risk_level: string | null;
  risk_score: number | null;
  decision: string | null;
  sync_state: string;
  sync_attempts: number;
  sync_last_attempt_at: string | null;
  sync_last_synced_at: string | null;
  sync_last_error: string | null;
  officer_id: string;
  officer_name: string;
  unit: string;
  post_name: string;
  scenario_id: string | null;
  stages_payload: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentRow {
  id: string;
  case_id: string;
  kind: string;
  declared_type: string | null;
  image_uri: string;
  image_width: number;
  image_height: number;
  image_bytes: number;
  capture_source: string;
  captured_at: string;
  analysis_payload: string | null;
}

export interface PayloadRow {
  case_id: string;
  payload: string;
}

export interface DecisionRow {
  id: string;
  case_id: string;
  decision: string;
  remarks: string;
  officer_id: string;
  officer_name: string;
  decided_at: string;
  risk_level_at_decision: string;
  risk_score_at_decision: number;
  diverged: number;
}

export interface AuditRow {
  id: string;
  case_id: string | null;
  type: string;
  description: string;
  actor_id: string;
  actor_name: string;
  occurred_at: string;
  metadata: string;
}

export interface SyncQueueRow {
  id: string;
  case_id: string;
  operation: string;
  state: string;
  attempts: number;
  last_error: string | null;
  next_retry_at: string | null;
  enqueued_at: string;
  updated_at: string;
}

export interface CountRow {
  count: number;
}
