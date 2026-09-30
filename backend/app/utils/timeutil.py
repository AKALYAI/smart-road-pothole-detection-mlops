"""app/utils/timeutil.py — naive-UTC "now" without the utcnow() deprecation."""
import datetime


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
