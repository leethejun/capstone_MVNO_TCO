import React, { useState } from 'react';
import { X, UserCheck, Mail, ArrowRight } from 'lucide-react';
import { createUser, getUser } from '../api';

export default function UserModal({ isOpen, onClose, currentUser, onSelectUser }) {
  const [email, setEmail] = useState('');
  const [targetMonths, setTargetMonths] = useState(12);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!email.trim() || !email.includes('@')) {
      setError('올바른 이메일 주소를 입력해주세요.');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const newUser = await createUser({
        email: email.trim(),
        defaultTargetMonths: Number(targetMonths),
      });
      onSelectUser(newUser);
      onClose();
    } catch (err) {
      setError(err.message || '로그인/가입 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = async () => {
    setLoading(true);
    setError('');
    try {
      // 기본 시드 유저(user_id=1) 조회
      const user1 = await getUser(1);
      onSelectUser(user1);
      onClose();
    } catch {
      // 1번이 없으면 랜덤 데모 생성
      const demoEmail = `demo_${Date.now()}@mvno.com`;
      const newUser = await createUser({ email: demoEmail, defaultTargetMonths: 12 });
      onSelectUser(newUser);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-3xl w-full max-w-sm p-6 shadow-2xl relative animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-2xl bg-indigo-100 text-indigo-600 flex items-center justify-center">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-base text-slate-900">사용자 계정 설정</h3>
            <p className="text-xs text-slate-500">개인 맞춤형 환승 알림 및 요금제 관리</p>
          </div>
        </div>

        {currentUser && (
          <div className="mb-4 p-3 bg-slate-50 rounded-2xl border border-slate-200 text-xs">
            <span className="text-slate-500">현재 연결된 계정:</span>
            <p className="font-semibold text-slate-800 mt-0.5 truncate">{currentUser.email} (ID: {currentUser.user_id})</p>
          </div>
        )}

        <form onSubmit={handleCreate} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">이메일 주소</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                placeholder="hong@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-500 focus:bg-white transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">선호 약정/환승 주기</label>
            <select
              aria-label="환승 이용 주기"
              value={targetMonths}
              onChange={(e) => setTargetMonths(Number(e.target.value))}
              className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:border-indigo-500"
            >
              {[6, 12, 24, 36, 48].map((m) => <option key={m} value={m}>{m}개월</option>)}
            </select>
          </div>

          {error && <p className="text-[11px] text-rose-500">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition shadow-xs disabled:opacity-50"
          >
            {loading ? '연결 중...' : '이 이메일로 시작하기'}
          </button>
        </form>

        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-200"></div>
          </div>
          <div className="relative flex justify-center text-[10px] uppercase">
            <span className="bg-white px-2 text-slate-400 font-medium">또는</span>
          </div>
        </div>

        <button
          type="button"
          onClick={handleQuickDemo}
          disabled={loading}
          className="w-full py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs flex items-center justify-center gap-1.5 transition"
        >
          <span>1초 만에 데모 계정으로 시작</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
