import { useI18n } from '../i18n/hooks';
import React, { useState } from 'react';
import { X, UserCheck } from 'lucide-react';
import { googleLogin, firebaseLogout, firebaseConfigured } from '../firebase';
import { updatePreferences } from '../api';
import { disablePush } from '../push';

export default function UserModal({ isOpen, onClose, currentUser, onSelectUser }) {
  const { t } = useI18n();
  const [targetMonths, setTargetMonths] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  if (!isOpen) return null;
  const run = async (action) => {
    setLoading(true); setError('');
    try { await action(); } catch (err) { setError(err.message || t("계정 처리 실패")); }
    finally { setLoading(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-3xl w-full max-w-sm p-6 shadow-2xl relative space-y-4">
        <button onClick={onClose} aria-label={t("닫기")} className="absolute top-4 right-4 text-slate-400"><X className="w-5 h-5" /></button>
        <h3 className="font-bold text-base flex items-center gap-2"><UserCheck className="w-5 h-5 text-indigo-600" />{t("사용자 계정")}</h3>
        {currentUser ? <>
          <p className="text-xs text-slate-600 break-all">{currentUser.email}</p>
          <label className="block text-xs font-semibold">{t("선호 환승 주기")} <select value={targetMonths ?? currentUser.default_target_months} onChange={(e) => setTargetMonths(Number(e.target.value))} className="mt-2 w-full p-2.5 border rounded-xl">
              {[6, 12, 24, 36, 48].map((m) => <option key={m} value={m}>{t("{{months}}개월", { months: m })}</option>)}
            </select>
          </label>
          <button disabled={loading} onClick={() => run(async () => {
            onSelectUser(await updatePreferences(targetMonths ?? currentUser.default_target_months)); onClose();
          })} className="w-full py-2.5 bg-indigo-600 text-white rounded-xl text-xs font-semibold disabled:opacity-50">{t("이용 주기 저장")}</button>
          <button disabled={loading} onClick={() => run(async () => {
            await disablePush(); await firebaseLogout(); onSelectUser(null); setTargetMonths(null); onClose();
          })} className="w-full py-2.5 bg-slate-100 rounded-xl text-xs disabled:opacity-50">{t("로그아웃")}</button>
        </> : <>
          <p className="text-xs text-slate-500">{t("Google 계정으로 로그인하여 내 요금제와 환승 알림을 관리하세요.")}</p>
          <button disabled={loading || !firebaseConfigured} onClick={() => run(async () => { await googleLogin(); onClose(); })} className="w-full py-3 bg-indigo-600 text-white rounded-xl text-xs font-bold disabled:opacity-50">
            {loading ? t("로그인 중...") : t("Google로 로그인")}
          </button>
          {!firebaseConfigured && <p className="text-xs text-slate-500">{t("Google 로그인 설정을 준비 중입니다.")}</p>}
        </>}
        {error && <p role="alert" className="text-xs text-rose-600">{t(error)}</p>}
      </div>
    </div>
  );
}
