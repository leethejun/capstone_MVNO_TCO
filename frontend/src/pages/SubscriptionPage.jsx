import React, { useState, useEffect } from 'react';
import { getUserSubscriptions, deleteSubscription } from '../api';
import { Calendar, CheckCircle2, Clock, ShieldAlert, PlusCircle, Trash2 } from 'lucide-react';

export default function SubscriptionPage({ currentUser, onNavigateToRank, onOpenUserModal }) {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState('');

  const handleDelete = async (sub) => {
    if (!window.confirm('이 요금제를 삭제할까요? 관련 환승 알림도 함께 삭제됩니다.')) return;
    setDeletingId(sub.subscription_id);
    setDeleteError('');
    try {
      await deleteSubscription({ subscriptionId: sub.subscription_id, userId: currentUser.user_id });
      setSubscriptions((items) => items.filter((item) => item.subscription_id !== sub.subscription_id));
    } catch (err) {
      setDeleteError(err.message || '요금제 삭제 실패');
    } finally {
      setDeletingId(null);
    }
  };

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
        <p className="text-xs text-slate-500 mb-5">내 요금제의 유지기간 종료일과 환승 알림을 확인하세요.</p>
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
          <p className="text-xs text-slate-500">유지기간 종료 한 달 전·일주일 전·하루 전에 알림을 드립니다</p>
        </div>
        <button
          onClick={onNavigateToRank}
          className="text-xs text-indigo-600 font-semibold flex items-center gap-1 hover:underline"
        >
          <PlusCircle className="w-4 h-4" />
          <span>추가 등록</span>
        </button>
      </div>

      {deleteError && <p role="alert" className="text-xs text-rose-600">{deleteError}</p>}
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
            현재 이용 중인 요금제를 등록하면,<br />선택한 유지기간 종료 한 달 전부터 최적의 환승 요금제를 추천해 드립니다.
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
          const dDay = calculateDday(sub.target_end_date);
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
                      {isExpired ? '선택한 유지기간이 종료되었습니다' : '선택한 유지기간 종료까지'}
                    </span>
                    <span className="font-black text-lg leading-none">
                      {isExpired ? `D+${Math.abs(dDay)}일 경과` : dDay === 0 ? 'D-Day (오늘 종료)' : `D-${dDay}일`}
                    </span>
                  </div>
                </div>

                <div className="text-right text-[11px]">
                  <span className="text-slate-500 block">유지기간 종료일</span>
                  <span className="font-bold text-slate-800">{sub.target_end_date}</span>
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
                  <span>{plan.discount_months === -1 ? '평생 할인' : `할인 종료일: ${sub.discount_end_date}`}</span>
                  {normalPrice > discountPrice && (
                    <span className="text-rose-500 font-semibold">
                      만료 후 월 {(normalPrice - discountPrice).toLocaleString()}원 추가 청구
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="text-slate-500">유지기간 {sub.target_months}개월</span>
                <button
                  type="button"
                  onClick={() => handleDelete(sub)}
                  disabled={deletingId !== null}
                  className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  {deletingId === sub.subscription_id ? '삭제 중...' : '요금제 삭제'}
                </button>
              </div>
              {/* 환승 알림 스케줄 타임라인 */}
              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-800 mb-2.5 block">환승 알림 예약 현황</span>
                <div className="grid grid-cols-3 gap-1.5">
                  {notifications.map((notif) => {
                    const isSent = notif.status === 'SENT';
                    const noticeTitle =
                      ({ MONTH_BEFORE: '한 달 전', 'D-7': '일주일 전', 'D-1': '하루 전',
                         'D-14': '이전 D-14', 'D-3': '이전 D-3' })[notif.notice_type] || notif.notice_type;

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
