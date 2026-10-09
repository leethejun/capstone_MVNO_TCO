import { test } from 'node:test';
import assert from 'node:assert/strict';
import { translate } from '../src/i18n/core.js';

test('English placeholders retain months and KRW without conversion', () => {
  assert.equal(translate('{{months}}개월', { months: 12 }, 'en'), '12 months');
  assert.equal(translate('{{price}}원/월', { price: '9,900' }, 'en'), '9,900 KRW/mo');
  assert.equal(translate('{{months}}개월', { months: 12 }, 'ko'), '12개월');
});
test('Original Korean plan and carrier names are preserved', () => {
  const name = '[K]5G 울트라(300분/15GB)';
  assert.equal(translate(name, {}, 'en'), name);
  assert.equal(translate('큰사람커넥트', {}, 'en'), '큰사람커넥트');
});
