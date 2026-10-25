"""Simplified parser for OpenStreetMap `opening_hours`.

Handles the common forms seen on Indian shops, pharmacies and petrol pumps:
  "24/7", "Mo-Su 08:00-23:00", "Mo-Sa 09:00-13:00,16:00-21:00; Su off", "18:00-02:00".
Anything it can't understand returns None, which the engine treats as UNKNOWN
instead of guessing.
"""
import re

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_DAY_SPEC = r"(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?"
_RULE = re.compile(rf"^((?:{_DAY_SPEC})(?:\s*,\s*{_DAY_SPEC})*)?\s*(.*)$")
_SPAN = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\+?$")


def _expand_days(spec):
    days = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            i, j = DAYS.index(a), DAYS.index(b)
            k = i
            while True:
                days.append(k)
                if k == j:
                    break
                k = (k + 1) % 7
        else:
            days.append(DAYS.index(part))
    return days


def parse(text):
    """Return {weekday: [(start_min, end_min), ...]} or None if unparseable.

    end_min can exceed 1440 for spans that run past midnight.
    Days not mentioned are closed (OSM semantics).
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if text == "24/7":
        return {d: [(0, 1440)] for d in range(7)}

    schedule = {}
    for rule in text.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        if rule.startswith("PH"):  # public-holiday rules are ignored
            continue
        m = _RULE.match(rule)
        if not m:
            return None
        day_spec, times = m.group(1), m.group(2).strip()
        days = _expand_days(day_spec) if day_spec else list(range(7))

        if times in ("off", "closed"):
            spans = []
        elif times == "":
            return None
        elif times in ("24/7", "00:00-24:00"):
            spans = [(0, 1440)]
        else:
            spans = []
            for piece in times.split(","):
                sm = _SPAN.match(piece.strip())
                if not sm:
                    return None
                h1, m1, h2, m2 = map(int, sm.groups())
                if h1 > 24 or h2 > 48 or m1 > 59 or m2 > 59:
                    return None
                start, end = h1 * 60 + m1, h2 * 60 + m2
                if end <= start:
                    end += 1440
                spans.append((start, end))
        for d in days:
            schedule[d] = spans
    return schedule


def is_open(schedule, dt):
    """True / False for a parsed schedule at datetime dt, None if schedule is None."""
    if schedule is None:
        return None
    minute = dt.hour * 60 + dt.minute
    today = dt.weekday()
    for start, end in schedule.get(today, []):
        if start <= minute < end:
            return True
    yesterday = (today - 1) % 7
    for start, end in schedule.get(yesterday, []):
        if end > 1440 and minute < end - 1440:
            return True
    return False


def open_at(text, dt):
    return is_open(parse(text), dt)
