import React, { useState, useEffect } from 'react';
import { getUserSubscriptions, triggerNotificationBatch } from '../api';
import { Bell, BellRing, Sparkles, Check, Send } from 'lucide-react';

export default function NotificationPage({ currentUser, onOpenUserModal }) {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState('');
  const [browserNotifPermission, setBrowserNotifPermission] = useState('default');

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
    if ('Notification' in window) {
      setBrowserNotifPermission(Notification.permission);
    }
  }, [currentUser]);

  // 브라우저 알림 권한 요청
  const requestBrowserPermission = async () => {
    if (!('Notification' in window)) {
      alert('이 브라우저는 웹 알림을 지원하지 않습니다.');
      return;
    }
    const perm = await Notification.requestPermission();
    setBrowserNotifPermission(perm);
    if (perm === 'granted') {
      new Notification('알뜰알뜰 환승 알리미', {
        body: '브라우저 환승 알림이 활성화되었습니다! D-Day에 알림을 전송합니다.',
        icon: '/vite.svg',
      });
    }
  };

  // 즉시 알림 배치 수동 실행 (시연용)
  const handleTriggerBatch = async () => {
    setTriggering(true);
    setTriggerResult('');
    try {
      const res = await triggerNotificationBatch();
      setTriggerResult(`배치 실행 성공: ${res.sent_count || 0}건 발송됨`);
      await loadData(); // 갱신된 SENT 상태 및 추천 요금제 리로드

      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🚨 [D-Day 환승 알림 도착]', {
          body: '프로모션 만료가 도래했습니다! 월 비용을 절약할 수 있는 TCO 최적 요금제를 확인하세요.',
          icon: '/vite.svg',
        });
      }
    } catch (err) {
      setTriggerResult(`실패: ${err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  if (!currentUser) {
    return (
      <div className="pt-20 px-6 text-center max-w-sm mx-auto">
        <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-3xl flex items-center justify-center mx-auto mb-4">
          <Bell className="w-7 h-7" />
        </div>
        <h3 className="font-bold text-base text-slate-900 mb-1">로그인이 필요합니다</h3>
        <p className="text-xs text-slate-500 mb-5">수신된 환승 알림과 TCO 1위 추천 요금제를 확인하세요.</p>
        <button
          onClick={onOpenUserModal}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold text-xs shadow-md transition"
        >
          1초 만에 시작하기
        </button>
      </div>
    );
  }

  // 모든 구독에서 알림 모음
  const allNotifications = [];
  subscriptions.forEach((sub) => {
    const notifs = sub.notifications || [];
    notifs.forEach((notif) => {
      allNotifications.push({ ...notif, currentPlan: sub.plan });
    });
  });

  return (
    <div className="pb-24 pt-2 px-4 space-y-4 max-w-md mx-auto">
      {/* 상단 알림 설정 & 데모 배치 트리거 카드 */}
      <div className="bg-gradient-to-br from-indigo-900 via-indigo-800 to-indigo-950 text-white rounded-3xl p-5 shadow-lg space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BellRing className="w-5 h-5 text-indigo-300" />
            <h3 className="font-bold text-sm">생애주기 환승 알림 센터</h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/20 font-medium">
            실시간 연동
          </span>
        </div>

        <p className="text-xs text-indigo-200 leading-relaxed">
          매일 자정에 프로모션 만료일을 자동 감지하여, 스펙(QoS, 데이터)이 유사한 <strong>TCO 최저가 대체 요금제</strong>를 선별 발송합니다.
        </p>

        {/* 브라우저 푸시 권한 버튼 */}
        <div className="pt-1 flex gap-2">
          {browserNotifPermission !== 'granted' ? (
            <button
              onClick={requestBrowserPermission}
              className="flex-1 py-2 px-3 bg-white text-indigo-900 rounded-xl text-xs font-bold hover:bg-indigo-50 transition shadow-xs flex items-center justify-center gap-1.5"
            >
              <Bell className="w-3.5 h-3.5 text-indigo-600" />
              <span>웹 브라우저 알림 켜기</span>
            </button>
          ) : (
            <div className="flex-1 py-1.5 px-3 bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span>브라우저 알림 활성화됨</span>
            </div>
          )}

          {/* 시연용 즉시 발송 버튼 */}
          <button
            onClick={handleTriggerBatch}
            disabled={triggering}
            className="py-2 px-3 bg-indigo-700 hover:bg-indigo-600 border border-indigo-500/40 text-white rounded-xl text-xs font-semibold transition flex items-center justify-center gap-1.5 disabled:opacity-50"
            title="오늘 날짜 기준 배치 즉시 수동 실행 (시연용)"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{triggering ? '발송 중...' : '배치 시연'}</span>
          </button>
        </div>

        {triggerResult && (
          <p className="text-[11px] text-amber-300 bg-black/20 p-2 rounded-xl text-center">{triggerResult}</p>
        )}
      </div>

      {/* 알림 피드 리스트 */}
      <div className="space-y-3">
        <h4 className="font-bold text-xs text-slate-700 px-1">도착한 환승 알림 & 추천 요금제</h4>

        {loading ? (
          <div className="py-16 text-center text-slate-400 text-xs">알림 내역 로딩 중...</div>
        ) : allNotifications.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-400 text-xs">
            수신된 환승 알림이 없습니다.
          </div>
        ) : (
          allNotifications.map((notif) => {
            const hasRecommendation = !!notif.recommended_plan;
            const currentPlan = notif.currentPlan || {};
            const recPlan = notif.recommended_plan || {};
            const noticeTypeStr = String(notif.notice_type || '').replace('_', '-');

            const currentNormalPrice = Number(currentPlan.normal_price || 0);
            const recDiscountPrice = Number(recPlan.discount_price || 0);

            return (
              <div
                key={notif.notification_id}
                className="bg-white rounded-3xl border border-slate-200/90 p-4.5 shadow-xs space-y-3"
              >
                {/* 알림 헤더 */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        notif.notice_type === 'D_3'
                          ? 'bg-rose-100 text-rose-700'
                          : notif.notice_type === 'D_7'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-indigo-100 text-indigo-700'
                      }`}
                    >
                      {noticeTypeStr} 알림
                    </span>
                    <span className="text-[11px] text-slate-400">{notif.scheduled_date}</span>
                  </div>

                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      notif.status === 'SENT'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-100 text-slate-500'
                    }`}
                  >
                    {notif.status === 'SENT' ? '발송 완료' : '발송 대기'}
                  </span>
                </div>

                {/* 현재 요금제 정보 */}
                <div className="text-xs">
                  <span className="text-slate-400 text-[10px]">현재 이용 중인 요금제</span>
                  <p className="font-bold text-slate-800 text-sm mt-0.5">{currentPlan.title || '기존 요금제'}</p>
                </div>

                {/* 자동 추천된 TCO 1위 대체 요금제 카드 */}
                {hasRecommendation ? (
                  <div className="bg-gradient-to-br from-indigo-50/90 via-indigo-50/40 to-white rounded-2xl border border-indigo-200/80 p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-900 flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                        TCO 최적 1위 추천 요금제
                      </span>
                      <span className="text-[10px] font-semibold bg-indigo-600 text-white px-2 py-0.5 rounded-full">
                        환승 추천
                      </span>
                    </div>

                    <p className="font-bold text-xs text-slate-900">{recPlan.title}</p>

                    <div className="flex items-center justify-between text-xs pt-1 border-t border-indigo-100/70">
                      <div>
                        <span className="text-[10px] text-slate-400 block">할인가격</span>
                        <span className="font-black text-indigo-600 text-sm">{recDiscountPrice.toLocaleString()}원/월</span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block">기본 데이터 / QoS</span>
                        <span className="font-semibold text-slate-700">
                          {recPlan.base_data_gb || 0}GB {recPlan.qos_speed_mbps > 0 && `+${recPlan.qos_speed_mbps}Mbps`}
                        </span>
                      </div>
                    </div>

                    {/* 비용 절감 비교 */}
                    {currentNormalPrice > recDiscountPrice && (
                      <div className="p-2 bg-emerald-50 text-emerald-800 rounded-xl text-[11px] font-semibold flex items-center justify-between mt-1">
                        <span>환승 시 매월 절감액</span>
                        <span className="font-bold">
                          -{(currentNormalPrice - recDiscountPrice).toLocaleString()}원 / 월
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-100 text-xs text-slate-500 text-center">
                    자정 배치 시 현재 요금제 스펙을 분석하여 최적의 대체 요금제가 매핑됩니다.
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
