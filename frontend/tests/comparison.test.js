import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { transformWithOxc } from 'vite';
import { translate } from '../src/i18n/core.js';

test('comparison shows the ranking period in English and retains original names', async () => {
  let source = await readFile(new URL('../src/components/ComparePlanModal.jsx', import.meta.url), 'utf8');
  source = source.replace("import { useI18n } from '../i18n/hooks';", `const useI18n = () => ({ locale: 'en', t: ${translate.toString()} });`);
  // Use the real dictionary while replacing the network boundary for static rendering.
  const english = JSON.parse(await readFile(new URL('../src/i18n/en.json', import.meta.url), 'utf8'));
  source = `const english = ${JSON.stringify(english)}; const getLocale = () => 'en';\n` + source;
  source = source.replace("import { getUserSubscriptions } from '../api';", 'const getUserSubscriptions = async () => [];');
  source = source.replace(/from 'react'/g, `from '${import.meta.resolve('react')}'`).replace(/from 'lucide-react'/g, `from '${import.meta.resolve('lucide-react')}'`);
  const { code } = await transformWithOxc(source, 'ComparePlanModal.jsx', { jsx: { runtime: 'classic' } });
  const { default: Modal } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
  const plan = { plan_id: 7, target_months: 48, title: '원문 요금제', telecom: { name: '통신사 원문' }, discount_price: 10000, normal_price: 20000, discount_months: -1 };
  const html = renderToStaticMarkup(React.createElement(Modal, { plan, currentUser: null }));
  for (const text of ['Estimated 48-month total', '480,000', 'KRW', '원문 요금제', '통신사 원문', 'Sign in and register']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /요금제 상세 비교|현재 유지|정보 없음/);
  assert.equal(renderToStaticMarkup(React.createElement(Modal, { plan: null })), '');
});
