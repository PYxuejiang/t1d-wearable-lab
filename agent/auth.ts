import { createHmac, timingSafeEqual } from 'node:crypto';

export function requireSecret(value: string | undefined, name: string): string {
  if (!value || !/^[a-f\d]{64}$/i.test(value)) throw new Error(`${name} must be 32 random bytes encoded as hex`);
  return value;
}

export function issueToken(subject: string, secret: string): string {
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(subject) || subject === 'knowledge') throw new Error('Invalid pseudonymous user id');
  return `${subject}.${createHmac('sha256', secret).update(subject).digest('base64url')}`;
}

export function authenticate(header: string | undefined, secret: string): string | undefined {
  if (!header?.startsWith('Bearer ')) return undefined;
  const token = header.slice(7);
  const [subject] = token.split('.');
  try {
    const expected = Buffer.from(issueToken(subject, secret));
    const actual = Buffer.from(token);
    return expected.length === actual.length && timingSafeEqual(expected, actual) ? subject : undefined;
  } catch {
    return undefined;
  }
}
