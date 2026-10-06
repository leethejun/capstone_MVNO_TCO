import React, { useState, useEffect } from 'react';
import { getUserSubscriptions } from '../api';
import { Calendar, CheckCircle2, Clock, ShieldAlert, PlusCircle } from 'lucide-react';

export default function SubscriptionPage({ currentUser, onNavigateToRank, onOpenUserModal }) {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    if (!currentUser) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await getUserSubscriptions(currentUser.user_id);
      setSubscriptions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setSubscriptions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentUser]);

  if (!currentUser) {
    return (
      <div className="pt-20 px-6 text-center max-w-sm mx-auto">
        <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-3xl flex items-center justify-center mx-auto mb-4">
          <Calendar className="w-7 h-7" />
        </div>
        <h3 className="font-bold text-base text-slate-900 mb-1">로그인이 필요합니다</h3>
        <p className="text-xs text-slate-500 mb-5">내 요금제의 프로모션 만료일과 D-Day 환승 알림을 확인하세요.</p>
        <button
          onClick={onOpenUserModal}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold text-xs shadow-md transition"
        >
          1초 만에 시작하기
        </button>
      </div>
    );
  }

  const calculateDday = (endDateStr) => {
    if (!endDateStr) return 0;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const end = new Date(endDateStr);
    end.setHours(0, 0, 0, 0);
    const diffTime = end - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  return (
    <div className="pb-24 pt-2 px-4 space-y-4 max-w-md mx-auto">
      <div className="flex items-center justify-between px-1">
        <div>
          <h2 className="font-bold text-base text-slate-900">내 요금제 생애주기 관리</h2>
          <p className="text-xs text-slate-500">프로모션 만료 전 최적의 타이밍에 알림을 드립니다</p>
        </div>
        <button
          onClick={onNavigateToRank}
          className="text-xs text-indigo-600 font-semibold flex items-center gap-1 hover:underline"
        >
          <PlusCircle className="w-4 h-4" />
          <span>추가 등록</span>
        </button>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400 text-xs">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          구독 정보 로딩 중...
        </div>
      ) : subscriptions.length === 0 ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-8 text-center shadow-xs">
          <div className="w-12 h-12 bg-slate-100 text-slate-400 rounded-2xl flex items-center justify-center mx-auto mb-3">
            <Calendar className="w-6 h-6" />
          </div>
          <h4 className="font-bold text-sm text-slate-800 mb-1">등록된 요금제가 없습니다</h4>
          <p className="text-xs text-slate-500 mb-5 leading-relaxed">
            현재 이용 중인 요금제를 등록하면,<br />할인 종료 전 위약금 없는 최적의 환승 요금제를 추천해 드립니다.
          </p>
          <button
            onClick={onNavigateToRank}
            className="py-2.5 px-5 bg-indigo-600 text-white rounded-xl font-bold text-xs shadow-xs hover:bg-indigo-700 transition"
          >
            요금제 랭킹에서 등록하기
          </button>
        </div>
      ) : (
        subscriptions.map((sub) => {
          const dDay = calculateDday(sub.discount_end_date);
          const isUrgent = dDay <= 7 && dDay >= 0;
          const isExpired = dDay < 0;
          const plan = sub.plan || {};
          const telecomName = plan.telecom?.name || '알뜰폰';
          const discountPrice = Number(plan.discount_price || 0);
          const normalPrice = Number(plan.normal_price || discountPrice);
          const notifications = sub.notifications || [];

          return (
            <div key={sub.subscription_id} className="bg-white rounded-3xl border border-slate-200/90 p-5 shadow-xs space-y-4">
              {/* 상단 D-Day 배너 */}
              <div
                className={`p-3.5 rounded-2xl flex items-center justify-between ${
                  isExpired
                    ? 'bg-rose-50 text-rose-800 border border-rose-100'
                    : isUrgent
                    ? 'bg-amber-50 text-amber-900 border border-amber-100'
                    : 'bg-indigo-50 text-indigo-900 border border-indigo-100'
                }`}
              >
                <div className="flex items-center gap-2">
                  {isExpired || isUrgent ? (
                    <ShieldAlert className="w-5 h-5 text-rose-500" />
                  ) : (
                    <Clock className="w-5 h-5 text-indigo-600" />
                  )}
                  <div>
                    <span className="text-[11px] font-medium block">
                      {isExpired ? '할인이 이미 만료되었습니다!' : '프로모션 할인 만료까지'}
                    </span>
                    <span className="font-black text-lg leading-none">
                      {isExpired ? `D+${Math.abs(dDay)}일 경과` : dDay === 0 ? 'D-Day (오늘 만료)' : `D-${dDay}일`}
                    </span>
                  </div>
                </div>

                <div className="text-right text-[11px]">
                  <span className="text-slate-500 block">할인 종료일</span>
                  <span className="font-bold text-slate-800">{sub.discount_end_date}</span>
                </div>
              </div>

              {/* 요금제 상세 카드 */}
              <div>
                <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-wide">
                  {telecomName}
                </span>
                <h3 className="font-bold text-base text-slate-900 mt-0.5">{plan.title || '등록된 요금제'}</h3>

                <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 text-xs">
                  <div className="bg-slate-50 p-2.5 rounded-xl">
                    <span className="text-slate-400 text-[10px] block">현재 월 할인 납부액</span>
                    <span className="font-bold text-slate-900 text-sm">{discountPrice.toLocaleString()}원</span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-xl">
                    <span className="text-slate-400 text-[10px] block">할인 만료 후 정상 요금</span>
                    <span className="font-bold text-rose-600 text-sm">{normalPrice.toLocaleString()}원</span>
                  </div>
                </div>

                {/* 만료 후 요금 인상 경고문 */}
                <div className="mt-2 text-[11px] text-slate-500 flex items-center justify-between px-1">
                  <span>할인 기간: {plan.discount_months || 12}개월간</span>
                  {normalPrice > discountPrice && (
                    <span className="text-rose-500 font-semibold">
                      만료 후 월 {(normalPrice - discountPrice).toLocaleString()}원 추가 청구
                    </span>
                  )}
                </div>
              </div>

              {/* 환승 알림 스케줄 타임라인 */}
              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-800 mb-2.5 block">환승 알림 예약 현황</span>
                <div className="grid grid-cols-3 gap-1.5">
                  {notifications.map((notif) => {
                    const isSent = notif.status === 'SENT';
                    const noticeTitle =
                      notif.notice_type === 'D_14' ? 'D-14 사전탐색' : notif.notice_type === 'D_7' ? 'D-7 준비' : 'D-3 즉시환승';

                    return (
                      <div
                        key={notif.notification_id}
                        className={`p-2.5 rounded-xl border text-center transition ${
                          isSent
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                            : 'bg-slate-50 border-slate-200 text-slate-600'
                        }`}
                      >
                        <span className="text-[10px] font-bold block mb-0.5">{noticeTitle}</span>
                        <span className="text-[10px] block text-slate-500 mb-1">{notif.scheduled_date}</span>
                        <div className="flex items-center justify-center gap-1 text-[10px] font-semibold">
                          {isSent ? (
                            <>
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span className="text-emerald-700">발송완료</span>
                            </>
                          ) : (
                            <>
                              <Clock className="w-3 h-3 text-slate-400" />
                              <span className="text-slate-500">대기중</span>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
