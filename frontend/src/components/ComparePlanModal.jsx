import React, { useEffect, useState } from 'react';
import { ArrowRight, ArrowLeftRight, X } from 'lucide-react';
import { useI18n } from '../i18n/hooks';
import { getUserSubscriptions } from '../api';

const present = (v) => v !== null && v !== undefined && v !== '';

function priceTotal(plan, months, elapsedMonths = 0) {
  const discount = Number(plan?.discount_price);
  const normal = present(plan?.normal_price) ? Number(plan.normal_price) : null;
  const period = Number(plan?.discount_months);
  if (!present(plan?.discount_price) || !present(plan?.discount_months) ||
      ![discount, period].every(Number.isFinite) || discount < 0 || period < -1) return null;
  if (normal === null) {
    if (period !== -1 && elapsedMonths + months > period) return null;
  } else if (!Number.isFinite(normal) || normal <= 0 || normal < discount) return null;
  let total = 0;
  for (let month = 0; month < months; month++) total += (period === -1 || elapsedMonths + month < period) ? discount : normal;
  return total;
}
function elapsedWholeMonths(startDate) {
  if (!startDate) return 0;
  const start = new Date(`${String(startDate).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(start.getTime())) return 0;
  const today = new Date();
  let months = (today.getFullYear() - start.getFullYear()) * 12 + today.getMonth() - start.getMonth();
  if (today.getDate() < start.getDate()) months--;
  return Math.max(0, months);
}
export default function ComparePlanModal(props) {
  if (!props.plan) return null;
  // A new plan/account gets fresh state before its first render, including logout.
  return <ComparisonSession key={`${props.currentUser?.user_id ?? 'guest'}:${props.plan.plan_id}:${props.plan.target_months ?? 12}`} {...props} />;
}

function ComparisonSession({ plan, currentUser, onClose, onRegister }) {
  const { t, locale } = useI18n();
const money = (value) => value == null ? t('정보 없음') : t('{{price}}원', { price: Math.round(value).toLocaleString(locale === 'en' ? 'en-US' : 'ko-KR') });
const fmtNumber = (v) => Number(v).toLocaleString(locale === 'en' ? 'en-US' : 'ko-KR', { maximumFractionDigits: 2 });
const fmtData = (p) => !present(p?.base_data_gb) ? '정보 없음' : `${fmtNumber(p.base_data_gb)}GB`;
const fmtDaily = (p) => !present(p?.daily_data_gb) ? '정보 없음' : Number(p.daily_data_gb) > 0 ? t('매일 {{data}}GB', { data: fmtNumber(p.daily_data_gb) }) : '없음';
const fmtQos = (p) => !present(p?.qos_speed_mbps) ? '정보 없음' : Number(p.qos_speed_mbps) > 0 ? `${fmtNumber(p.qos_speed_mbps)}Mbps` : '없음';
const fmtVoice = (p) => !present(p?.voice_minutes) ? '정보 없음' : Number(p.voice_minutes) === -1 ? '무제한' : t('{{minutes}}분', { minutes: fmtNumber(p.voice_minutes) });
const fmtSms = (p) => !present(p?.sms_count) ? '정보 없음' : Number(p.sms_count) === -1 ? '무제한' : t('{{count}}건', { count: fmtNumber(p.sms_count) });
const fmtPeriod = (p) => !present(p?.discount_months) ? '정보 없음' : Number(p.discount_months) === -1 ? '평생 할인' : t('{{months}}개월', { months: fmtNumber(p.discount_months) });
const fmtTelecom = (p) => p?.telecom?.name || '정보 없음';

  const [subscriptions, setSubscriptions] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [months, setMonths] = useState([6, 12, 24, 36, 48].includes(plan.target_months) ? plan.target_months : 12);
  const [loading, setLoading] = useState(Boolean(currentUser));
  const [error, setError] = useState('');
  useEffect(() => {
    if (!plan || !currentUser) return;
    let cancelled = false;
    setLoading(true); setError('');
    getUserSubscriptions(currentUser.user_id).then((data) => {
      if (cancelled) return;
      const items = Array.isArray(data) ? data.filter((s) => s.plan) : [];
      setSubscriptions(items);
      setSelectedId(items.length ? String(items[0].subscription_id) : '');
    }).catch((err) => { if (!cancelled) { setSubscriptions([]); setSelectedId(''); setError(err.message || '내 요금제를 불러오지 못했습니다.'); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [plan, currentUser]);
  if (!plan) return null;
  const current = subscriptions.find((s) => String(s.subscription_id) === selectedId);
  const oldPlan = current?.plan;
  const oldTotal = current ? priceTotal(oldPlan, months, elapsedWholeMonths(current.start_date)) : null;
  const newTotal = priceTotal(plan, months);
  const rows = [
    ['제공 통신사', fmtTelecom],
    ['네트워크 방식', p => p?.network_type || '정보 없음'],
    ['기본 데이터', fmtData],
    ['일일 추가 데이터', fmtDaily],
    ['소진 후 QoS', fmtQos],
    ['통화', fmtVoice],
    ['문자', fmtSms],
    ['할인 월 요금', p => present(p?.discount_price) ? money(Number(p.discount_price)) : '정보 없음'],
    ['할인 기간', fmtPeriod],
    ['할인 종료 후 월 요금', p => present(p?.normal_price) ? money(Number(p.normal_price)) : '정보 없음'],
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-label={t("현재 요금제와 상세 비교")} className="bg-white rounded-3xl w-full max-w-md max-h-[90vh] overflow-y-auto p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-base flex items-center gap-2 text-slate-900"><ArrowLeftRight className="w-5 h-5 text-indigo-600" />{t("요금제 상세 비교")}</h2>
          <button type="button" aria-label={t("닫기")} onClick={onClose} className="p-1.5 text-slate-500"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-xs text-slate-500">{t("내 요금제와 선택한 요금제의 제공량 및 비용을 비교합니다. 자동 추천·종합 점수는 계산하지 않습니다.")}</p>
        <div className="space-y-1">
          <label htmlFor="compare-months" className="block text-xs font-semibold text-slate-700">{t("비교 기간")}</label>
          <select id="compare-months" value={months} onChange={(e) => setMonths(Number(e.target.value))} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs">
            {[6, 12, 24, 36, 48].map((n) => <option value={n} key={n}>{t("{{months}}개월", { months: n })}</option>)}
          </select>
        </div>
        {loading && <p className="text-xs text-slate-500">{t("내 요금제 조회 중...")}</p>}
        {error && <p role="alert" className="text-xs text-rose-600">{t(error)}</p>}
        {!currentUser && <p className="text-xs bg-amber-50 text-amber-800 p-3 rounded-xl">{t("로그인 후 내 요금제를 등록하면 비교할 수 있습니다.")}</p>}
        {currentUser && !loading && !error && subscriptions.length === 0 && <p className="text-xs bg-amber-50 text-amber-800 p-3 rounded-xl">{t("등록된 내 요금제가 없습니다. ‘내 요금제’에서 먼저 등록해 주세요.")}</p>}
        {subscriptions.length > 0 && <div className="space-y-1">
          <label htmlFor="compare-current" className="block text-xs font-semibold text-slate-700">{t("비교할 내 요금제")}</label>
          <select id="compare-current" value={selectedId} onChange={(e) => setSelectedId(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs">
            {subscriptions.map((s) => <option key={s.subscription_id} value={String(s.subscription_id)}>{s.plan?.title || t('이름 없는 요금제')}</option>)}
          </select>
        </div>}
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-2">
          {[{ label: '현재 내 요금제', p: oldPlan, tint: 'bg-slate-50 border-slate-200' }, { label: '선택한 요금제', p: plan, tint: 'bg-indigo-50 border-indigo-200' }].map((item) => <div key={item.label} className={`rounded-xl border p-3 min-w-0 ${item.tint}`}>
            <p className="text-[11px] font-bold text-slate-600">{t(item.label)}</p>
            <p className="text-xs font-semibold break-words mt-1">{item.p?.title || t('미등록')}</p>
          </div>)}
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-200">
          <table className="w-full table-fixed text-[11px] text-slate-800">
            <colgroup><col style={{ width: '34%' }} /><col style={{ width: '33%' }} /><col style={{ width: '33%' }} /></colgroup>
            <thead><tr className="bg-slate-100"><th className="text-left p-2">{t("비교 항목")}</th><th className="text-left p-2">{t("현재")}</th><th className="text-left p-2">{t("선택")}</th></tr></thead>
            <tbody>{rows.map(([label, render]) => {
              const a = oldPlan ? render(oldPlan) : '미등록';
              const b = render(plan);
              const different = oldPlan && a !== b && a !== '정보 없음' && b !== '정보 없음';
              return <tr key={label} className="border-t border-slate-100">
                <th scope="row" className="p-2 text-left font-semibold text-slate-600 break-words">{t(label)}</th>
                <td className="p-2 break-words">{t(a)}</td>
                <td className={`p-2 break-words ${different ? 'bg-indigo-50 font-semibold text-indigo-800' : ''}`}>{t(b)}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
        <div className="rounded-xl border border-slate-200 p-3 space-y-2">
          <p className="text-xs font-bold text-slate-700">{t("{{months}}개월 예상 총비용 (TCO)", { months })}</p>
          <div className="grid grid-cols-2 gap-2 text-center">
            <div><p className="text-[11px] text-slate-500">{t("현재 유지")}</p><p className="text-sm font-black">{money(oldTotal)}</p></div>
            <div><p className="text-[11px] text-slate-500">{t("선택 요금제 개통")}</p><p className="text-sm font-black text-indigo-700">{money(newTotal)}</p></div>
          </div>
          {oldTotal !== null && newTotal !== null && <p className="text-center text-xs font-semibold text-slate-700">{t("비용 차이: {{price}} ({{result}})", { price: money(Math.abs(oldTotal - newTotal)), result: t(oldTotal > newTotal ? "선택 요금제가 저렴" : oldTotal < newTotal ? "현재 요금제가 저렴" : "동일") })}</p>}
        </div>
        <p className="text-[10px] leading-relaxed text-slate-500">{t("* 현재 요금제는 경과 개월 수를 반영하며, 일할 청구·유심비·해지 비용은 포함하지 않습니다.")}</p>
        <button type="button" onClick={onRegister} className="w-full py-3 rounded-xl bg-indigo-600 text-white text-xs font-bold flex items-center justify-center gap-2">{t("이 요금제로 개통 등록")}<ArrowRight className="w-4 h-4" /></button>
      </div>
    </div>
  );
}
