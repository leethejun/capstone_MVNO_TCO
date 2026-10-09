import english from './en.json' with { type: 'json' };
export const languageKey = 'alddle_language';
export function getLocale() {
  try { return localStorage.getItem(languageKey) === 'en' ? 'en' : 'ko'; }
  catch { return 'ko'; }
}
export function translate(text, values = {}, locale = getLocale()) {
  if (typeof text !== 'string') return '';
  const template = locale === 'en' ? english[text] || text : text;
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => String(values[key] ?? ''));
}
