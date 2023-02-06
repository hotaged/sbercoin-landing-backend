from api.config import settings
from tortoise.timezone import get_timezone, make_aware
from datetime import datetime, date, time, timedelta


winpay_time = time(
        settings.winpay.hour,
        settings.winpay.minute,
        settings.winpay.second,
        settings.winpay.microsecond,
    )


def is_valid_bid(bid_datetime: datetime) -> bool:
    winpay = bid_datetime.replace(
        hour=winpay_time.hour,
        minute=winpay_time.minute,
        second=winpay_time.second,
        microsecond=winpay_time.microsecond
    )

    return bid_datetime <= winpay


def seconds_remains() -> int:
    winpay = next_winpay()
    now = make_aware(datetime.now(), get_timezone())

    return (winpay - now).seconds


def next_winpay() -> datetime:
    winpay_day = date.today()

    if datetime.combine(winpay_day, winpay_time) < datetime.now():
        winpay_day = winpay_day + timedelta(days=1)

    return make_aware(datetime.combine(winpay_day, winpay_time), get_timezone())
