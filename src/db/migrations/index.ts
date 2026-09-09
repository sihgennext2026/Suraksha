import type { SQLiteDatabase } from 'expo-sqlite';

export interface Migration {
  /** Target `user_version` after this migration applies. */
  version: number;
  name: string;
  up(db: SQLiteDatabase): Promise<void>;
}

/**
 * Schema for offline case storage.
 *
 * Design notes:
 *  - Each analysis result gets its own table, mirroring the domain model, so a
 *    future backend can stream stages independently.
 *  - Every result table keeps queryable summary columns *and* a `payload` JSON
 *    column holding the full typed result. Lists and filters read the columns;
 *    detail screens rehydrate the payload. This avoids both N-way joins on the
 *    list path and lossy storage on the detail path.
 *  - `ON DELETE CASCADE` throughout: purging a case removes every trace of it
 *    in one statement, which is what the retention policy will need.
 */
const initialSchema: Migration = {
  version: 1,
  name: 'initial-schema',
  async up(db) {
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY NOT NULL,
        officer_id    TEXT NOT NULL UNIQUE,
        name          TEXT NOT NULL,
        rank          TEXT NOT NULL,
        role          TEXT NOT NULL,
        unit          TEXT NOT NULL,
        post_name     TEXT NOT NULL,
        device_id     TEXT NOT NULL,
        last_login_at TEXT
      );

      CREATE TABLE IF NOT EXISTS cases (
        id                     TEXT PRIMARY KEY NOT NULL,
        status                 TEXT NOT NULL,
        document_type          TEXT NOT NULL,
        subject_name           TEXT,
        masked_document_number TEXT,
        risk_level             TEXT,
        risk_score             REAL,
        decision               TEXT,
        sync_state             TEXT NOT NULL DEFAULT 'LOCAL_ONLY',
        sync_attempts          INTEGER NOT NULL DEFAULT 0,
        sync_last_attempt_at   TEXT,
        sync_last_synced_at    TEXT,
        sync_last_error        TEXT,
        officer_id             TEXT NOT NULL,
        officer_name           TEXT NOT NULL,
        unit                   TEXT NOT NULL,
        post_name              TEXT NOT NULL,
        scenario_id            TEXT,
        stages_payload         TEXT NOT NULL DEFAULT '[]',
        created_at             TEXT NOT NULL,
        updated_at             TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases (created_at DESC);
      CREATE INDEX IF NOT EXISTS idx_cases_status     ON cases (status);
      CREATE INDEX IF NOT EXISTS idx_cases_risk_level ON cases (risk_level);
      CREATE INDEX IF NOT EXISTS idx_cases_sync_state ON cases (sync_state);
      CREATE INDEX IF NOT EXISTS idx_cases_doc_type   ON cases (document_type);

      CREATE TABLE IF NOT EXISTS documents (
        id               TEXT PRIMARY KEY NOT NULL,
        case_id          TEXT NOT NULL,
        kind             TEXT NOT NULL,
        declared_type    TEXT,
        image_uri        TEXT NOT NULL,
        image_width      INTEGER NOT NULL,
        image_height     INTEGER NOT NULL,
        image_bytes      INTEGER NOT NULL,
        capture_source   TEXT NOT NULL,
        captured_at      TEXT NOT NULL,
        analysis_payload TEXT,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_documents_case ON documents (case_id);

      CREATE TABLE IF NOT EXISTS ocr_results (
        case_id            TEXT PRIMARY KEY NOT NULL,
        overall_confidence REAL NOT NULL,
        mrz_present        INTEGER NOT NULL,
        mrz_checksum_valid INTEGER NOT NULL,
        payload            TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS validation_results (
        case_id       TEXT PRIMARY KEY NOT NULL,
        overall       TEXT NOT NULL,
        passed_count  INTEGER NOT NULL,
        warning_count INTEGER NOT NULL,
        failed_count  INTEGER NOT NULL,
        payload       TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS face_results (
        case_id          TEXT PRIMARY KEY NOT NULL,
        similarity_score REAL NOT NULL,
        decision         TEXT NOT NULL,
        payload          TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS forensic_results (
        case_id               TEXT PRIMARY KEY NOT NULL,
        verdict               TEXT NOT NULL,
        tampering_probability REAL NOT NULL,
        payload               TEXT NOT NULL,
        created_at            TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS anomaly_results (
        case_id       TEXT PRIMARY KEY NOT NULL,
        verdict       TEXT NOT NULL,
        anomaly_score REAL NOT NULL,
        payload       TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS risk_results (
        case_id    TEXT PRIMARY KEY NOT NULL,
        score      REAL NOT NULL,
        level      TEXT NOT NULL,
        payload    TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE TABLE IF NOT EXISTS officer_decisions (
        id                     TEXT PRIMARY KEY NOT NULL,
        case_id                TEXT NOT NULL,
        decision               TEXT NOT NULL,
        remarks                TEXT NOT NULL DEFAULT '',
        officer_id             TEXT NOT NULL,
        officer_name           TEXT NOT NULL,
        decided_at             TEXT NOT NULL,
        risk_level_at_decision TEXT NOT NULL,
        risk_score_at_decision REAL NOT NULL,
        diverged               INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_decisions_case ON officer_decisions (case_id);

      CREATE TABLE IF NOT EXISTS audit_events (
        id          TEXT PRIMARY KEY NOT NULL,
        case_id     TEXT,
        type        TEXT NOT NULL,
        description TEXT NOT NULL,
        actor_id    TEXT NOT NULL,
        actor_name  TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        metadata    TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events (case_id, occurred_at);
      CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events (occurred_at DESC);

      CREATE TABLE IF NOT EXISTS sync_queue (
        id            TEXT PRIMARY KEY NOT NULL,
        case_id       TEXT NOT NULL UNIQUE,
        operation     TEXT NOT NULL,
        state         TEXT NOT NULL,
        attempts      INTEGER NOT NULL DEFAULT 0,
        last_error    TEXT,
        next_retry_at TEXT,
        enqueued_at   TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_sync_state ON sync_queue (state, next_retry_at);

      CREATE TABLE IF NOT EXISTS case_sequence (
        year     INTEGER PRIMARY KEY NOT NULL,
        last_seq INTEGER NOT NULL
      );
    `);
  },
};

/**
 * Replaces the six per-module result tables with one row holding the canonical
 * case document.
 *
 * The old tables encoded the previous contract in their column names -
 * `tampering_probability`, `verdict`, a 0-100 `score` - and those concepts no
 * longer exist. A case screened before this migration cannot be rendered
 * correctly by the new screens whatever we do with its rows, so keeping the
 * tables would preserve data that is already unreadable while implying the
 * columns still mean something. They are dropped, and the drop is the honest
 * record of a contract change.
 *
 * From here the application stores exactly what the screening service returned,
 * unmodified. Queryable facts the case list needs stay denormalised onto
 * `cases`; everything else is read back out of the document.
 */
const canonicalCaseResult: Migration = {
  version: 2,
  name: 'canonical-case-result',
  async up(db) {
    await db.execAsync(`
      CREATE TABLE IF NOT EXISTS case_results (
        case_id        TEXT PRIMARY KEY NOT NULL,
        schema_version TEXT NOT NULL,
        payload        TEXT NOT NULL,
        generated_at   TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases (id) ON DELETE CASCADE
      );

      DROP TABLE IF EXISTS ocr_results;
      DROP TABLE IF EXISTS validation_results;
      DROP TABLE IF EXISTS face_results;
      DROP TABLE IF EXISTS forensic_results;
      DROP TABLE IF EXISTS anomaly_results;
      DROP TABLE IF EXISTS risk_results;
    `);
  },
};

export const MIGRATIONS: readonly Migration[] = [initialSchema, canonicalCaseResult];

export const LATEST_SCHEMA_VERSION = MIGRATIONS.reduce(
  (max, migration) => Math.max(max, migration.version),
  0,
);
