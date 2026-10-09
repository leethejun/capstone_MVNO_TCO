import { useI18n } from '../i18n/hooks';
import React, { useState } from 'react';
import { X, Calendar, CheckCircle2 } from 'lucide-react';
import { createSubscription } from '../api';

export default function SubscribeModal({ isOpen, onClose, plan, currentUser, onSuccess }) {
  const { t } = useI18n();
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [targetMonths, setTargetMonths] = useState(12);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !plan) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!currentUser) {
      setError(t("사용자 로그인이 필요합니다."));
      return;
    }
    setLoading(true);
    setError('');

    try {
      const res = await createSubscription({
        userId: currentUser.user_id,
        planId: plan.plan_id,
        startDate,
        targetMonths: Number(targetMonths),
      });
      onSuccess(res);
      onClose();
    } catch (err) {
      setError(err.message || t("등록 중 오류가 발생했습니다."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-3xl w-full max-w-sm p-6 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onClose}
          aria-label={t("닫기")}
          className="absolute top-4 right-4 p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-base text-slate-900">{t("내 요금제 개통 등록")}</h3>
            <p className="text-xs text-slate-500">{t("유지기간 종료 전 환승 알림이 자동 예약됩니다")}</p>
          </div>
        </div>

        <div className="mb-4 p-3 bg-slate-50 rounded-2xl border border-slate-200 text-xs space-y-1">
          <span className="text-[10px] font-semibold text-indigo-600 uppercase tracking-wider">{plan.telecom_name}</span>
          <p className="font-bold text-slate-900 text-sm">{plan.title}</p>
          <div className="flex justify-between items-center pt-1 text-slate-600 border-t border-slate-200/60 mt-1">
            <span>{t("월 할인 납부액")}</span>
            <span className="font-bold text-indigo-600">{(plan.discount_price || 0).toLocaleString()}{t("원")}</span>
          </div>
          {Number(plan.normal_price || 0) > Number(plan.discount_price || 0) && (
            <div className="flex justify-between items-center text-slate-500 text-[11px]">
              <span>{t("할인 만료 후 정상 요금")}</span>
              <span className="font-semibold text-rose-600">{Number(plan.normal_price).toLocaleString()}{t("원/월")}</span>
            </div>
          )}
          <div className="flex justify-between items-center text-slate-500 text-[11px]">
            <span>{t("프로모션 할인 기간")}</span>
            <span>{plan.discount_months === -1 ? t("평생 할인") : t("{{months}}개월간", { months: plan.discount_months || 12 })}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">{t("개통일자 선택")}</label>
            <div className="relative">
              <Calendar className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-500 focus:bg-white transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">{t("예상 이용 주기 (약정 개월)")}</label>
            <select
              aria-label={t("환승 이용 주기")}
              value={targetMonths}
              onChange={(e) => setTargetMonths(Number(e.target.value))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:border-indigo-500"
            >
              {[6, 12, 24, 36, 48].map((m) => <option key={m} value={m}>{t("{{months}}개월", { months: m })}</option>)}
            </select>
          </div>

          <div className="p-2.5 bg-indigo-50/70 border border-indigo-100 rounded-xl text-[11px] text-indigo-800 leading-relaxed">
            🔔 <strong>{t("안내:")}</strong> {t("개통 등록 시 선택한 유지기간 종료")} <strong>{t("한 달 전·일주일 전·하루 전")}</strong>{' '}{t("에 환승 알림이 예약됩니다. 추천 요금제는 유지기간 종료 한 달 전부터 표시됩니다.")} </div>

          {error && <p className="text-[11px] text-rose-500">{t(error)}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition shadow-xs disabled:opacity-50"
          >
            {loading ? t("등록 중...") : t("구독 요금제로 등록하기")}
          </button>
        </form>
      </div>
    </div>
  );
}
