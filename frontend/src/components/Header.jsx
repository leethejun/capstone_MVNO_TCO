import { useI18n } from '../i18n/hooks';
import React from 'react';
import { User, Sparkles } from 'lucide-react';

export default function Header({ user, onOpenUserModal }) {
  const { t, locale, setLocale } = useI18n();
  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 px-4 py-3 flex items-center justify-between shadow-xs">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-xs">
          <Sparkles className="w-4 h-4" />
        </div>
        <div>
          <h1 className="font-bold text-base tracking-tight text-slate-900 leading-none">{t("알뜰알뜰")} <span className="text-xs font-semibold text-indigo-600 px-1.5 py-0.5 rounded-full bg-indigo-50 border border-indigo-100">TCO</span>
          </h1>
          <p className="text-[10px] text-slate-500 mt-0.5">{t("알뜰폰 환승 생애주기 알리미")}</p>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
      <select aria-label="Language / 언어" value={locale} onChange={(event) => setLocale(event.target.value)} className="rounded-lg border border-slate-200 bg-white text-[11px] px-1 py-1.5">
        <option value="ko">한국어</option><option value="en">English</option>
      </select>
      <button
        onClick={onOpenUserModal}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 text-xs font-medium text-slate-700 transition"
      >
        <User className="w-3.5 h-3.5 text-slate-500" />
        <span className="max-w-[70px] truncate">
          {user ? user.email.split('@')[0] : t("로그인")}
        </span>
      </button>
      </div>
    </header>
  );
}
