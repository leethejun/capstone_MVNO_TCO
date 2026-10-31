import { test } from 'node:test';
import assert from 'node:assert/strict';
import { translate } from '../src/i18n/core.js';
import { describeReason } from '../src/recommendation-reasons.js';
import {
  favoriteIdentity, favoriteKey, loadGuestFavorites, saveGuestFavorites, sortFavoritesByTco, toggleGuestFavorite,
} from '../src/favorites.js';

function memoryStorage() {
  const values = new Map();
  return { getItem: (k) => values.get(k) ?? null, setItem: (k, v) => values.set(k, String(v)) };
}

test('guest favorites toggle by carrier, title and network instead of plan_id', () => {
  const plan = { plan_id: 1, title: '든든 7GB', network_type: 'LTE', telecom: { name: '프리티' } };
  const recrawled = { ...plan, plan_id: 99 };
  let items = toggleGuestFavorite([], plan);
  assert.equal(items.length, 1);
  assert.equal(favoriteIdentity(items[0]), favoriteIdentity(recrawled));
  items = toggleGuestFavorite(items, recrawled);
  assert.deepEqual(items, []);
});

test('guest favorites survive storage round trip and ignore broken data', () => {
  const storage = memoryStorage();
  saveGuestFavorites([favoriteKey({ plan_id: 3, title: 'A', telecom_name: '모빙' })], storage);
  assert.equal(loadGuestFavorites(storage)[0].telecom_name, '모빙');
  storage.setItem('alddle_favorites', '{not json');
  assert.deepEqual(loadGuestFavorites(storage), []);
});

test('favorites list orders computable plans by TCO first', () => {
  const sorted = sortFavoritesByTco([
    { title: 'none', status: 'unavailable' }, { title: 'b', plan: { tco: 200 } }, { title: 'a', plan: { tco: 100 } },
  ]);
  assert.deepEqual(sorted.map((i) => i.title), ['a', 'b', 'none']);
});

test('recommendation reasons render Korean and English text with formatted values', () => {
  const ko = (text, values) => translate(text, values, 'ko');
  const en = (text, values) => translate(text, values, 'en');
  const increase = { code: 'price_increase', params: { after_months: 7, from_price: 3300, normal_months: 5, to_price: 18700 } };
  assert.equal(describeReason(increase, ko, 'ko'), '7개월 동안 월 3,300원, 이후 5개월은 정상가 월 18,700원이 적용됩니다.');
  assert.equal(describeReason(increase, en, 'en'), '3,300 KRW/mo for 7 months, then the regular 18,700 KRW/mo for 5 months.');
  const tie = { code: 'tie_break', params: { criterion: 'qos' } };
  assert.match(describeReason(tie, ko, 'ko'), /소진 후 속도 조건이 더 좋아/);
  assert.equal(describeReason({ code: 'filters_matched', params: {} }, ko, 'ko'), null);
  assert.equal(describeReason({ code: 'unknown_code' }, ko, 'ko'), null);
});
