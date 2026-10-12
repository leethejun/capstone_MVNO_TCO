import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createAccountSession, logoutAccount } from '../src/account-session.js';

test('login and observer share account resolution and wait for it', async () => {
  let resolve, calls = 0;
  const published = [];
  const session = createAccountSession({ getAccount: () => { calls++; return new Promise(r => { resolve = r; }); }, publish: value => published.push(value), reportError() {} });
  const first = session.load({ uid: 'user' });
  const second = session.load({ uid: 'user' });
  assert.equal(first, second);
  await Promise.resolve();
  assert.equal(calls, 1);
  assert.deepEqual(published, [null]);
  resolve({ email: 'user@example.com' });
  await second;
  assert.equal(published.at(-1).email, 'user@example.com');
});

test('a late account response cannot restore a logged out user', async () => {
  let resolve;
  const published = [];
  const session = createAccountSession({ getAccount: () => new Promise(r => { resolve = r; }), publish: value => published.push(value), reportError() {} });
  const login = session.load({ uid: 'user' });
  await Promise.resolve();
  session.clear();
  resolve({ email: 'user@example.com' });
  await login;
  assert.deepEqual(published, [null, null]);
});

for (const [label, cleanup] of [['failed', async () => { throw new Error('push unavailable'); }], ['stalled', () => new Promise(() => {})]]) {
  test(`logout completes even if push cleanup ${label}`, async () => {
    const calls = [];
    await logoutAccount({ cleanup, signOut: async () => calls.push('signOut'), clear: () => calls.push('clear'), timeoutMs: 5 });
    assert.deepEqual(calls, ['signOut', 'clear']);
  });
}

test('Firebase logout failure remains visible and does not clear the account', async () => {
  let cleared = false;
  await assert.rejects(logoutAccount({ cleanup: async () => {}, signOut: async () => { throw new Error('logout failed'); }, clear: () => { cleared = true; } }), /logout failed/);
  assert.equal(cleared, false);
});
