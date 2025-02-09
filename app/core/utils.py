import datetime
import string
import random
from typing import Optional, ClassVar


def utc_now_float() -> float:
    now = datetime.datetime.utcnow()
    return datetime_to_float(now)


def datetime_to_float(d) -> float:
    epoch = datetime.datetime.utcfromtimestamp(0)
    total_seconds = (d - epoch).total_seconds()
    return total_seconds


def float_to_datetime(fl) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(fl)


def secs_delta(t1: Optional[float], t2: Optional[float]) -> Optional[float]:
    if not (t1 and t2):
        return None
    return abs(t1 - t2)


def datetime_delta(
    t1: Optional[float], t2: Optional[float]
) -> Optional[datetime.timedelta]:
    if not (t1 and t2):
        return None
    if t1 > t2:
        diff = float_to_datetime(t1) - float_to_datetime(t2)
    else:
        diff = float_to_datetime(t2) - float_to_datetime(t1)
    return diff


def load_class(class_path: str) -> ClassVar:
    components = class_path.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def generate_digit_str(n: int = 4) -> str:
    accum = ''
    for i in range(n):
        accum += random.choice(string.digits)
    return accum


def trim_account_uid(s) -> str:
    return s.strip().replace(' ', '').replace('(', '').replace(')', '').replace('-', '')  # noqa
