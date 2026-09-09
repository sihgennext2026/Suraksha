import type { AuditEvent, AuditEventType, CaseId } from '@/types';
import { nowIso } from '@/utils/date';
import { newId } from '@/utils/id';

import { getDatabase, parsePayload } from '../client';
import type { AuditRow } from '../rows';

export interface RecordAuditInput {
  caseId: CaseId | null;
  type: AuditEventType;
  description: string;
  actorId: string;
  actorName: string;
  metadata?: Record<string, string | number | boolean>;
}

/**
 * Append-only record of everything that happened to a case.
 *
 * There is deliberately no update or delete for individual events: the audit
 * trail is evidence, and the only way an event leaves the device is when its
 * entire case is purged under the retention policy.
 */
export interface AuditRepository {
  record(input: RecordAuditInput): Promise<AuditEvent>;
  listForCase(caseId: CaseId): Promise<AuditEvent[]>;
  listRecent(limit?: number): Promise<AuditEvent[]>;
}

function toEvent(row: AuditRow): AuditEvent {
  return {
    id: row.id,
    caseId: row.case_id,
    type: row.type as AuditEventType,
    description: row.description,
    actorId: row.actor_id,
    actorName: row.actor_name,
    occurredAt: row.occurred_at,
    metadata: parsePayload<Record<string, string | number | boolean>>(row.metadata) ?? {},
  };
}

class SqliteAuditRepository implements AuditRepository {
  async record(input: RecordAuditInput): Promise<AuditEvent> {
    const event: AuditEvent = {
      id: newId(),
      caseId: input.caseId,
      type: input.type,
      description: input.description,
      actorId: input.actorId,
      actorName: input.actorName,
      occurredAt: nowIso(),
      metadata: input.metadata ?? {},
    };

    const db = await getDatabase();
    await db.runAsync(
      `INSERT INTO audit_events (id, case_id, type, description, actor_id, actor_name, occurred_at, metadata)
       VALUES (?,?,?,?,?,?,?,?)`,
      [
        event.id,
        event.caseId,
        event.type,
        event.description,
        event.actorId,
        event.actorName,
        event.occurredAt,
        JSON.stringify(event.metadata),
      ],
    );
    return event;
  }

  async listForCase(caseId: CaseId): Promise<AuditEvent[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<AuditRow>(
      'SELECT * FROM audit_events WHERE case_id = ? ORDER BY occurred_at ASC',
      [caseId],
    );
    return rows.map(toEvent);
  }

  async listRecent(limit = 50): Promise<AuditEvent[]> {
    const db = await getDatabase();
    const rows = await db.getAllAsync<AuditRow>(
      'SELECT * FROM audit_events ORDER BY occurred_at DESC LIMIT ?',
      [limit],
    );
    return rows.map(toEvent);
  }
}

export const auditRepository: AuditRepository = new SqliteAuditRepository();
