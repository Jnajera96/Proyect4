"""Fechas ISO para filtrar el planificador y los informes locales."""
from datetime import datetime, timedelta, timezone

def parse_date(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Missing date")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def in_range(moment, start, end):
    start, end = parse_date(start), parse_date(end)
    if end < start:
        raise ValueError("Invalid date range")
    return start <= parse_date(moment) <= end

def day_window(text):
    moment = parse_date(text)
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)
