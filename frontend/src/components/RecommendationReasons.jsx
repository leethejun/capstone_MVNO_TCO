import React from 'react';
import { Lightbulb } from 'lucide-react';
import { useI18n } from '../i18n/hooks';
import { describeReason } from '../recommendation-reasons';

export default function RecommendationReasons({ reasons, title = '추천 근거' }) {
  const { t, locale } = useI18n();
  const lines = (reasons || [])
    .map((reason) => ({ code: reason.code, text: describeReason(reason, t, locale) }))
    .filter((line) => line.text);
  if (!lines.length) return null;
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 space-y-1.5" onClick={(e) => e.stopPropagation()}>
      <p className="text-[11px] font-bold text-amber-900 flex items-center gap-1">
        <Lightbulb className="w-3.5 h-3.5" />{t(title)}
      </p>
      <ul className="space-y-1">
        {lines.map((line) => (
          <li
            key={line.code}
            className={line.code === 'tco_formula'
              ? 'text-[10px] font-mono text-slate-500 pt-1 border-t border-amber-100 break-words'
              : 'text-[11px] leading-relaxed text-slate-700 pl-3 relative before:content-["•"] before:absolute before:left-0 before:text-amber-500'}
          >
            {line.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
