import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { calculatePlanTco, calculateSubscriptionSavings, elapsedWholeMonths } from '../src/pages/subscriptionSavings.js';
import { translate } from '../src/i18n/core.js';

const today = new Date('2026-10-28T00:00:00');
const sixMonthPromo = { discount_price: 10000, normal_price: 30000, discount_months: 6 };
const flat20k = { discount_price: 20000, normal_price: 20000, discount_months: 0 };

test('elapsed whole months only counts completed months', () => {
  assert.equal(elapsedWholeMonths('2026-04-28', today), 6);
  assert.equal(elapsedWholeMonths('2026-04-29', today), 5);
  assert.equal(elapsedWholeMonths('2026-11-01', today), 0);
  assert.equal(elapsedWholeMonths(null, today), 0);
});

test('plan TCO skips discount months that were already used', () => {
  assert.equal(calculatePlanTco(sixMonthPromo, 12), 6 * 10000 + 6 * 30000);
  assert.equal(calculatePlanTco(sixMonthPromo, 12, 6), 360000);
  assert.equal(calculatePlanTco(sixMonthPromo, 12, 20), 360000);
  assert.equal(calculatePlanTco(sixMonthPromo, 12, 4), 2 * 10000 + 10 * 30000);
  assert.equal(calculatePlanTco({ ...sixMonthPromo, discount_months: -1 }, 12, 30), 120000);
  assert.equal(calculatePlanTco({ ...sixMonthPromo, normal_price: null }, 12), null);
});

test('savings use the remaining cost of the current plan (review example)', () => {
  // 6개월 할인이 이미 끝난 구독: 향후 12개월 유지비 36만원, 월 2만원 요금제는 24만원 → 12만원 절약.
  const sub = { plan: sixMonthPromo, target_months: 12, start_date: '2026-04-28' };
  assert.deepEqual(calculateSubscriptionSavings(sub, flat20k, today), { currentTco: 360000, recommendedTco: 240000, savings: 120000 });
  assert.equal(calculateSubscriptionSavings(sub, null, today), null);
});

test('savings card strings have English translations', async () => {
  const source = await readFile(new URL('../src/pages/SubscriptionPage.jsx', import.meta.url), 'utf8');
  for (const key of ['예상 절약 금액', '예상 비용 증가', '현재 요금제 예상 총비용', '추천 요금제 예상 총비용', '추천 요금제']) {
    assert.ok(source.includes(`t("${key}")`), key);
    assert.notEqual(translate(key, {}, 'en'), key, key);
  }
  const notice = '앞으로 {{months}}개월 기준으로 계산한 예상 금액입니다. 현재 요금제는 이미 지난 할인 기간을 반영합니다.';
  assert.ok(source.includes(notice));
  assert.match(translate(notice, { months: 12 }, 'en'), /next 12 months/);
});
