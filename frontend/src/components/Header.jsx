import { useI18n } from '../i18n/hooks';
import { User, Sparkles, ChevronDown } from 'lucide-react';

export default function Header({ user, onOpenUserModal }) {
  const { t, locale, setLocale } = useI18n();
  return (
    <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between gap-2 border-b border-slate-200/70 bg-white/95 px-3 py-2.5 backdrop-blur-md sm:px-4">
      <div className="flex shrink-0 items-center gap-2">
        <div aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-sm shadow-indigo-200">
          <Sparkles className="h-[18px] w-[18px]" />
        </div>
        <h1 className="flex items-baseline gap-1 text-[15px] font-bold tracking-tight text-slate-900">
          {t('알뜰알뜰')}
          <span className="text-[11px] font-semibold tracking-normal text-indigo-600">TCO</span>
        </h1>
      </div>

      <div className="flex min-w-0 items-center gap-1.5">
        <div className="relative shrink-0">
          <select
            aria-label="Language / 언어"
            value={locale}
            onChange={(event) => setLocale(event.target.value)}
            className="h-10 w-[76px] appearance-none rounded-xl border border-slate-200 bg-white pl-2 pr-5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
          >
            <option value="ko">한국어</option>
            <option value="en">English</option>
          </select>
          <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400" />
        </div>
        <button
          onClick={onOpenUserModal}
          aria-label={user ? t('사용자 계정') : t('로그인')}
          title={user?.email}
          className="flex h-10 min-w-10 items-center justify-center gap-1.5 rounded-xl border border-indigo-100 bg-indigo-50 px-2.5 text-xs font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        >
          <User aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span className="max-w-[44px] truncate sm:max-w-[70px]">
            {user ? user.email.split('@')[0] : t('로그인')}
          </span>
        </button>
      </div>
    </header>
  );
}
