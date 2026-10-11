import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/hooks';
import { getCrawlerRunState, startCrawlerRefresh } from '../api';

export default function AdminPage({ currentUser }) {
  const { t, locale } = useI18n();
  const [state, setState] = useState(null);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  useEffect(() => {
    if (!currentUser?.is_admin) return;
    let stopped = false;
    const load = async () => {
      try { const data = await getCrawlerRunState(); if (!stopped) { setState(data); setError(''); } }
      catch (err) { if (!stopped) setError(err.message); }
    };
    load();
    const timer = setInterval(load, 5000);
    return () => { stopped = true; clearInterval(timer); };
  }, [currentUser]);
  if (!currentUser?.is_admin) return <p className="p-5">{t('관리자 권한이 필요합니다.')}</p>;
  const refresh = async () => {
    setPending(true); setError('');
    try { setState(await startCrawlerRefresh()); }
    catch (err) { setError(err.message); }
    finally { setPending(false); }
  };
  const date = value => value ? new Date(value).toLocaleString(locale === 'en' ? 'en-US' : 'ko-KR', { timeZone: 'Asia/Seoul' }) : '—';
  const running = state?.status === 'running';
  const report = state?.result || state?.last_report;
  const next = state?.jobs?.find(job => job.id === 'monthly_mvno_crawler')?.next_run_time;
  const labels = { idle: '대기 중', running: '수집 중', completed: '갱신 완료', failed: '갱신 실패' };
  return <section className="p-4 pb-24 space-y-4">
    <h2 className="text-xl font-bold">{t('관리자 페이지')}</h2>
    <div className="rounded-xl bg-white border p-4 space-y-2 text-sm">
      <p>{t('자동 갱신: 매월 1일 새벽 2시 (한국 시간)')}</p>
      <p>{t('다음 자동 갱신')}: {date(next)}</p>
      <p>{t('상태')}: {t(labels[state?.status] || '대기 중')}</p>
      <p>{t('수집 시작')}: {date(state?.started_at)}</p>
      <p>{t('최근 수집')}: {date(state?.finished_at || report?.crawled_at)}</p>
      <button disabled={!state || pending || running} onClick={refresh} className="w-full bg-indigo-600 text-white rounded-lg py-3 disabled:opacity-50">{t(running ? '수집 중' : '전체 요금제 수동 갱신')}</button>
      <p className="text-xs text-slate-500">{t('전체 수집에는 시간이 걸립니다. 페이지를 닫아도 계속 진행됩니다. 검증이 완료되면 요금제 목록이 교체됩니다.')}</p>
    </div>
    {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
    {report && <div className="bg-white border rounded-xl p-4 space-y-2 text-sm">
      <h3 className="font-bold">{t('최근 수집 결과')}</h3>
      <p>{t(report.success ? '갱신 완료' : '갱신 실패')}</p>
      {report.error && <p role="alert" className="text-rose-600 break-words">{report.error}</p>}
      <p>{t('활성 요금제')}: {report.total_active_plans ?? '—'}</p>
      {report.coverage?.map(item => <div key={item.name} className="border-t pt-2">
        <p className="font-medium">{item.name}</p>
        <p>{t('공식몰')}: {item.official_count ?? 0} · {t('허브')}: {item.hub_count ?? 0}</p>
        {item.error && <p className="text-rose-600 break-words">{item.error}</p>}
      </div>)}
    </div>}
  </section>;
}
