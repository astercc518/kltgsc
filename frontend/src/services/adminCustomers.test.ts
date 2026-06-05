import { describe, it, expect } from 'vitest';
import { generateRandomPassword, AdminApiError } from './adminCustomers';

describe('generateRandomPassword', () => {
  it('returns 12 chars by default', () => {
    expect(generateRandomPassword()).toHaveLength(12);
  });

  it('returns the requested length', () => {
    expect(generateRandomPassword(16)).toHaveLength(16);
  });

  it('returns different values across calls (randomness sanity)', () => {
    const a = generateRandomPassword();
    const b = generateRandomPassword();
    expect(a).not.toBe(b);
  });
});

describe('AdminApiError', () => {
  it('preserves status and detail', () => {
    const err = new AdminApiError(409, { detail: 'dup' }, 'duplicate');
    expect(err.status).toBe(409);
    expect(err.detail).toEqual({ detail: 'dup' });
    expect(err.message).toBe('duplicate');
  });
});
