import { DatabaseSync } from 'node:sqlite';

/**
 * An in-memory stand-in for `expo-sqlite`, backed by Node's own SQLite.
 *
 * Repository tests are only worth writing if they exercise the SQL that will
 * actually run: the upsert conflict clauses, the cascade deletes, the index
 * usage, the migration itself. A hand-written fake would test the mock instead.
 * This adapter implements the slice of the `SQLiteDatabase` surface the
 * repositories use, over a real SQLite engine, so the schema in
 * `src/db/migrations` is genuinely executed.
 */

type BindValue = string | number | null | Uint8Array;

function normaliseParams(params: unknown[]): BindValue[] {
  // Callers pass either a single array of parameters or a variadic list; both
  // are flattened to the positional array node:sqlite expects.
  const flat = params.length === 1 && Array.isArray(params[0]) ? params[0] : params;
  return (flat as unknown[]).map((value) => {
    if (value === undefined || value === null) return null;
    if (typeof value === 'boolean') return value ? 1 : 0;
    return value as BindValue;
  });
}

export interface TestDatabase {
  execAsync(sql: string): Promise<void>;
  runAsync(
    sql: string,
    ...params: unknown[]
  ): Promise<{ changes: number; lastInsertRowId: number }>;
  getFirstAsync<T>(sql: string, ...params: unknown[]): Promise<T | null>;
  getAllAsync<T>(sql: string, ...params: unknown[]): Promise<T[]>;
  withTransactionAsync(task: () => Promise<void>): Promise<void>;
  closeAsync(): Promise<void>;
}

export function createTestDatabase(): TestDatabase {
  const db = new DatabaseSync(':memory:');
  let transactionDepth = 0;

  return {
    async execAsync(sql: string) {
      try {
        db.exec(sql);
      } catch (error) {
        // `exec` rejects statements that return rows, which some PRAGMAs do.
        // Those are re-run through a prepared statement so behaviour matches
        // expo-sqlite, where `execAsync` accepts them.
        if (/^\s*PRAGMA/i.test(sql)) {
          db.prepare(sql).all();
          return;
        }
        throw error;
      }
    },

    async runAsync(sql: string, ...params: unknown[]) {
      const result = db.prepare(sql).run(...normaliseParams(params));
      return {
        changes: Number(result.changes),
        lastInsertRowId: Number(result.lastInsertRowid),
      };
    },

    async getFirstAsync<T>(sql: string, ...params: unknown[]) {
      const row = db.prepare(sql).get(...normaliseParams(params));
      return (row as T) ?? null;
    },

    async getAllAsync<T>(sql: string, ...params: unknown[]) {
      return db.prepare(sql).all(...normaliseParams(params)) as T[];
    },

    async withTransactionAsync(task: () => Promise<void>) {
      // Nesting is flattened rather than using savepoints: the repositories
      // never rely on partial rollback of an inner block, and flattening keeps
      // the adapter's behaviour identical to a single outer transaction.
      if (transactionDepth > 0) {
        transactionDepth += 1;
        try {
          await task();
        } finally {
          transactionDepth -= 1;
        }
        return;
      }

      transactionDepth = 1;
      db.exec('BEGIN');
      try {
        await task();
        db.exec('COMMIT');
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      } finally {
        transactionDepth = 0;
      }
    },

    async closeAsync() {
      db.close();
    },
  };
}
