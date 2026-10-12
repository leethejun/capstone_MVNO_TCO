import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from services.lifecycle import target_end_date
from services.push import send_to_devices
from models import Notification, UserSubscription, Plan, User, NoticeType

class NotificationDispatcher:
    """
    환승 알림 멀티채널 발송기 (Discord Webhook, FCM, 콘솔 감사 로그)
    """

    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

    @classmethod
    def dispatch(
        cls,
        notification: Notification,
        subscription: UserSubscription,
        user: User,
        current_plan: Plan,
        recommended_plan: Optional[Plan],
        db=None
    ) -> Dict[str, Any]:
        """
        환승 알림 메시지를 생성하고 등록된 채널로 발송합니다.
        """
        title, body = cls._build_message(notification.notice_type, current_plan, target_end_date(subscription), recommended_plan)

        dispatch_result = {
            "notification_id": notification.notification_id,
            "user_email": user.email,
            "notice_type": notification.notice_type.value,
            "title": title,
            "body": body,
            "fcm_sent": False,
            "discord_sent": False,
            "console_logged": True,
            "sent_at": datetime.now().isoformat()
        }

        # 1. 콘솔 감사 로그 출력
        print("\n" + "=" * 70)
        print(f"📢 [알뜰폰 환승 알림 발송 - {notification.notice_type.value}]")
        print(f"• 수신자: {user.email}")
        print(f"• 현재 요금제: [{current_plan.telecom.name if current_plan.telecom else '알뜰폰'}] {current_plan.title}")
        print(f"• 유지기간 종료일: {target_end_date(subscription)}")
        if recommended_plan:
            rec_telecom = recommended_plan.telecom.name if recommended_plan.telecom else '알뜰폰'
            print(f"• 💡 추천 대체 요금제: [{rec_telecom}] {recommended_plan.title} (할인가: {recommended_plan.discount_price:,}원)")
        print(f"• 알림 내용: {title}")
        print(f"  {body}")
        print("=" * 70 + "\n")

        # 2. Discord Webhook 전송 (웹훅 URL이 설정되어 있을 때)
        if cls.DISCORD_WEBHOOK_URL:
            try:
                payload = {
                    "embeds": [{
                        "title": f"📱 [알뜰폰 환승 알림] {title}",
                        "description": body,
                        "color": 0xFF6B00 if notification.notice_type in (NoticeType.D_1, NoticeType.D_3) else 0x00A8FF,
                        "fields": [
                            {"name": "사용자", "value": user.email, "inline": True},
                            {"name": "현재 요금제", "value": current_plan.title, "inline": True},
                            {"name": "유지기간 종료일", "value": str(target_end_date(subscription)), "inline": True},
                        ],
                        "footer": {"text": "알뜰폰 TCO 최적화 알림 봇"}
                    }]
                }
                resp = requests.post(cls.DISCORD_WEBHOOK_URL, json=payload, timeout=5)
                if resp.status_code in [200, 204]:
                    dispatch_result["discord_sent"] = True
            except Exception as e:
                print(f"[NotificationDispatcher] Discord 전송 실패: {e}")

        # 사용자별 여러 기기에 실제 FCM 발송. 토큰 보유만으로 성공 처리하지 않는다.
        if db is not None:
            english_message = cls._build_message(notification.notice_type, current_plan, target_end_date(subscription), recommended_plan, language="en")
            push_result = send_to_devices(notification, user, title, body, db, english_message=english_message)
            dispatch_result['push'] = push_result
            dispatch_result['fcm_sent'] = push_result['sent'] > 0


        return dispatch_result

    @staticmethod
    def _build_message(
        notice_type: NoticeType,
        current_plan: Plan,
        end_date,
        rec_plan: Optional[Plan],
        language="ko"
    ) -> (str, str):
        if language == "en":
            timing = {NoticeType.MONTH_BEFORE: "one month", NoticeType.D_7: "7 days", NoticeType.D_1: "1 day",
                      NoticeType.D_14: "14 days", NoticeType.D_3: "3 days"}[notice_type]
            title = f"Your switching date is {timing} away!"
            recommendation = ""
            if rec_plan:
                telecom = rec_plan.telecom.name if rec_plan.telecom else "MVNO"
                recommendation = f"\nLowest-TCO recommendation: [{telecom}] {rec_plan.title} ({rec_plan.discount_price:,} KRW/mo)"
            return title, f"Your chosen usage period for '{current_plan.title}' ends on {end_date}.{recommendation}\nCompare plans before switching to save on mobile costs."
        timing = {NoticeType.MONTH_BEFORE: "한 달", NoticeType.D_7: "7일", NoticeType.D_1: "1일",
                  NoticeType.D_14: "14일", NoticeType.D_3: "3일"}[notice_type]
        title = f"요금제 유지기간 종료 {timing} 전입니다!"

        rec_text = ""
        if rec_plan:
            telecom = rec_plan.telecom.name if rec_plan.telecom else "알뜰폰"
            rec_text = f"\n👉 TCO 최저가 추천: [{telecom}] {rec_plan.title} (월 {rec_plan.discount_price:,}원)"

        body = (
            f"현재 이용 중이신 '{current_plan.title}' 요금제의 선택한 유지기간이 "
            f"{end_date}에 종료됩니다."
            f"{rec_text}\n더 늦기 전에 환승하여 통신비를 절약하세요!"
        )

        return title, body
