import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { DatabaseSync } from 'node:sqlite';

export class HealthStore {
  private database: DatabaseSync;
  private key: Buffer;

  constructor(directory: string, encryptionKey: string) {
    if (!/^[a-f\d]{64}$/i.test(encryptionKey)) throw new Error('HEALTH_DATA_KEY must be 32 random bytes encoded as hex');
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    this.key = Buffer.from(encryptionKey, 'hex');
    this.database = new DatabaseSync(resolve(directory, 'health.sqlite'));
    this.database.exec('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS records (subject TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(subject, kind, id))');
  }

  put(subject: string, kind: string, id: string, value: unknown): void {
    const nonce = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', this.key, nonce);
    cipher.setAAD(Buffer.from(JSON.stringify([subject, kind, id])));
    const ciphertext = Buffer.concat([cipher.update(JSON.stringify(value), 'utf8'), cipher.final()]);
    const payload = [nonce.toString('base64'), cipher.getAuthTag().toString('base64'), ciphertext.toString('base64')].join('.');
    this.database.prepare('INSERT OR REPLACE INTO records VALUES (?, ?, ?, ?)').run(subject, kind, id, payload);
  }

  get<T>(subject: string, kind: string, id: string): T | undefined {
    const row = this.database.prepare('SELECT payload FROM records WHERE subject=? AND kind=? AND id=?').get(subject, kind, id);
    if (!row) return undefined;
    const [nonce, tag, ciphertext] = String(row.payload).split('.').map(value => Buffer.from(value, 'base64'));
    const decipher = createDecipheriv('aes-256-gcm', this.key, nonce);
    decipher.setAAD(Buffer.from(JSON.stringify([subject, kind, id])));
    decipher.setAuthTag(tag);
    return JSON.parse(Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8')) as T;
  }

  list<T>(subject: string, kind: string): T[] {
    const rows = this.database.prepare('SELECT id FROM records WHERE subject=? AND kind=? ORDER BY id').all(subject, kind);
    return rows.map(row => this.get<T>(subject, kind, String(row.id))!);
  }

  subjects(): string[] {
    return this.database.prepare("SELECT DISTINCT subject FROM records WHERE kind='profile'").all().map(row => String(row.subject));
  }

  deleteSubject(subject: string): void {
    this.database.prepare('DELETE FROM records WHERE subject=?').run(subject);
  }

  transaction<T>(operation: () => T): T {
    this.database.exec('BEGIN IMMEDIATE');
    try {
      const result = operation();
      this.database.exec('COMMIT');
      return result;
    } catch (error) {
      this.database.exec('ROLLBACK');
      throw error;
    }
  }

  close(): void {
    this.database.close();
    this.key.fill(0);
  }
}
