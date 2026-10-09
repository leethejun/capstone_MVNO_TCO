"""선택한 요금제 유지기간을 기준으로 환승 시점을 계산한다."""
import calendar
from datetime import date, timedelta
from models import NoticeType, SubscriptionStatus


def shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def target_end_date(subscription) -> date:
    return shift_months(subscription.start_date, subscription.target_months)


def recommendation_start_date(subscription) -> date:
    return shift_months(target_end_date(subscription), -1)


def recommendation_available(subscription, today=None) -> bool:
    return (subscription.status == SubscriptionStatus.ACTIVE
            and (today or date.today()) >= recommendation_start_date(subscription))


def notification_schedule(subscription):
    end = target_end_date(subscription)
    return [(NoticeType.MONTH_BEFORE, shift_months(end, -1)),
            (NoticeType.D_7, end - timedelta(days=7)),
            (NoticeType.D_1, end - timedelta(days=1))]
