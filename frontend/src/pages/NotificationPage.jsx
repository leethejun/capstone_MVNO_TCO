import { useI18n } from '../i18n/hooks';
import React, { useState, useEffect } from 'react';
import { getUserSubscriptions } from '../api';
import { enablePush, disablePush, refreshPush, watchForegroundPush, sendTestPush } from '../push';
import { Bell, BellRing, Sparkles, Check } from 'lucide-react';

export default function NotificationPage({ currentUser, onOpenUserModal }) {
  const { t } = useI18n();
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushError, setPushError] = useState('');

  const loadData = async () => {
    if (!currentUser) {
      setSubscriptions([]);
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

  useEffect(() => {
    let disposed = false;
    let stop = () => {};
    setPushEnabled(false);
    if (currentUser) {
      refreshPush().then((enabled) => { if (!disposed) setPushEnabled(enabled); }).catch(() => {});
      watchForegroundPush(loadData).then((unsubscribe) => {
        if (disposed) unsubscribe(); else stop = unsubscribe;
      }).catch(() => {});
    }
    return () => { disposed = true; stop(); };
  }, [currentUser]);

  const requestBrowserPermission = async () => {
    setConnecting(true); setPushError('');
    try {
      await enablePush(); setPushEnabled(true);
    } catch (err) { setPushError(err.message || t("푸시 알림 연결 실패")); }
    finally { setConnecting(false); }
  };
  const testPush = async () => {
    setConnecting(true); setPushError('');
    try { await sendTestPush(); }
    catch (err) { setPushError(err.message || t("테스트 알림 전송 실패")); }
    finally { setConnecting(false); }
  };
  const turnOffPush = async () => {
    setConnecting(true); setPushError('');
    try { await disablePush(); setPushEnabled(false); }
    catch (err) { setPushError(err.message || t("알림 해제 실패")); }
    finally { setConnecting(false); }
  };

  if (!currentUser) {
    return (
      <div className="pt-20 px-6 text-center max-w-sm mx-auto">
        <div className="w-14 h-14 bg-indigo-50 text-indigo-600 rounded-3xl flex items-center justify-center mx-auto mb-4">
          <Bell className="w-7 h-7" />
        </div>
        <h3 className="font-bold text-base text-slate-900 mb-1">{t("로그인이 필요합니다")}</h3>
        <p className="text-xs text-slate-500 mb-5">{t("수신된 환승 알림과 TCO 1위 추천 요금제를 확인하세요.")}</p>
        <button
          onClick={onOpenUserModal}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold text-xs shadow-md transition"
        >{t("1초 만에 시작하기")} </button>
      </div>
    );
  }

  // 모든 구독에서 알림 모음
  const allNotifications = [];
  subscriptions.forEach((sub) => {
    const notifs = sub.notifications || [];
    notifs.forEach((notif) => {
      allNotifications.push({ ...notif, currentPlan: sub.plan, recommendationAvailable: sub.recommendation_available, recommendationStartDate: sub.recommendation_start_date });
    });
  });

  return (
    <div className="pb-24 pt-2 px-4 space-y-4 max-w-md mx-auto">
      {/* 상단 알림 설정 카드 */}
      <div className="bg-gradient-to-br from-indigo-900 via-indigo-800 to-indigo-950 text-white rounded-3xl p-5 shadow-lg space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BellRing className="w-5 h-5 text-indigo-300" />
            <h3 className="font-bold text-sm">{t("생애주기 환승 알림 센터")}</h3>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/20 font-medium">{t("실시간 연동")} </span>
        </div>

        <p className="text-xs text-indigo-200 leading-relaxed">{t("매일 자정에 유지기간 종료 한 달 전·일주일 전·하루 전에, 스펙(QoS, 데이터)이 유사한")} <strong>{t("TCO 최저가 대체 요금제")}</strong>{' '}{t("를 선별 발송합니다.")} </p>

        {/* 브라우저 푸시 권한 버튼 */}
        <div className="pt-1 flex gap-2">
          {!pushEnabled ? (
            <button
              onClick={requestBrowserPermission}
              disabled={connecting}
              className="flex-1 py-2 px-3 bg-white text-indigo-900 rounded-xl text-xs font-bold hover:bg-indigo-50 transition shadow-xs flex items-center justify-center gap-1.5"
            >
              <Bell className="w-3.5 h-3.5 text-indigo-600" />
              <span>{connecting ? t("연결 중...") : t("푸시 알림 켜기")}</span>
            </button>
          ) : (
            <div className="flex-1 py-1.5 px-3 bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5">
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span>{t("FCM 푸시 알림 연결됨")}</span>
            </div>
          )}

          {pushEnabled && <button disabled={connecting} onClick={turnOffPush} className="text-xs text-indigo-200 px-2">{t("이 기기 알림 끄기")}</button>}
        </div>

        {pushEnabled && <button disabled={connecting} onClick={testPush} className="text-xs text-indigo-200 underline">{t("테스트 알림 보내기")}</button>}
        {pushError && <p role="alert" className="text-xs text-amber-300">{t(pushError)}</p>}
      </div>

      {/* 알림 피드 리스트 */}
      <div className="space-y-3">
        <h4 className="font-bold text-xs text-slate-700 px-1">{t("도착한 환승 알림 & 추천 요금제")}</h4>

        {loading ? (
          <div className="py-16 text-center text-slate-400 text-xs">{t("알림 내역 로딩 중...")}</div>
        ) : allNotifications.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-400 text-xs">{t("수신된 환승 알림이 없습니다.")} </div>
        ) : (
          allNotifications.map((notif) => {
            const hasRecommendation = notif.recommendationAvailable && !!notif.recommended_plan;
            const currentPlan = notif.currentPlan || {};
            const recPlan = notif.recommended_plan || {};
            const noticeTypeStr = ({ MONTH_BEFORE: t("한 달 전"), 'D-7': t("일주일 전"), 'D-1': t("하루 전") })[notif.notice_type] || String(notif.notice_type || '').replace('_', '-');

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
                        notif.notice_type === 'D-1'
                          ? 'bg-rose-100 text-rose-700'
                          : notif.notice_type === 'D-7'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-indigo-100 text-indigo-700'
                      }`}
                    >
                      {t("{{timing}} 알림", { timing: noticeTypeStr })}
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
                    {notif.push_status === 'SENT' ? t("푸시 발송 완료") : notif.push_status === 'NO_DEVICE' ? t("앱 내 알림") : notif.status === 'FAILED' ? t("발송 실패") : t("발송 대기")}
                  </span>
                </div>

                {/* 현재 요금제 정보 */}
                <div className="text-xs">
                  <span className="text-slate-400 text-[10px]">{t("현재 이용 중인 요금제")}</span>
                  <p className="font-bold text-slate-800 text-sm mt-0.5">{currentPlan.title || t("기존 요금제")}</p>
                </div>

                {/* 자동 추천된 TCO 1위 대체 요금제 카드 */}
                {hasRecommendation ? (
                  <div className="bg-gradient-to-br from-indigo-50/90 via-indigo-50/40 to-white rounded-2xl border border-indigo-200/80 p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-indigo-900 flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5 text-indigo-600" />{t("TCO 최적 1위 추천 요금제")} </span>
                      <span className="text-[10px] font-semibold bg-indigo-600 text-white px-2 py-0.5 rounded-full">{t("환승 추천")} </span>
                    </div>

                    <p className="font-bold text-xs text-slate-900">{recPlan.title}</p>

                    <div className="flex items-center justify-between text-xs pt-1 border-t border-indigo-100/70">
                      <div>
                        <span className="text-[10px] text-slate-400 block">{t("할인가격")}</span>
                        <span className="font-black text-indigo-600 text-sm">{recDiscountPrice.toLocaleString()}{t("원/월")}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block">{t("기본 데이터 / QoS")}</span>
                        <span className="font-semibold text-slate-700">
                          {recPlan.base_data_gb || 0}GB {recPlan.qos_speed_mbps > 0 && `+${recPlan.qos_speed_mbps}Mbps`}
                        </span>
                      </div>
                    </div>

                    {/* 비용 절감 비교 */}
                    {currentNormalPrice > recDiscountPrice && (
                      <div className="p-2 bg-emerald-50 text-emerald-800 rounded-xl text-[11px] font-semibold flex items-center justify-between mt-1">
                        <span>{t("환승 시 매월 절감액")}</span>
                        <span className="font-bold">
                          -{(currentNormalPrice - recDiscountPrice).toLocaleString()}{t("원/월")}
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-2xl border border-slate-100 text-xs text-slate-500 text-center">
                    {notif.recommendationAvailable
                      ? t("예약된 알림 발송 시점에 최신 요금제를 비교하여 추천합니다.")
                      : t("추천 요금제는 유지기간 종료 한 달 전({{date}})부터 표시됩니다.", { date: notif.recommendationStartDate })}
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
