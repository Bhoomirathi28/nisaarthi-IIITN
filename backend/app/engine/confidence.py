"""Data-confidence labels required by the problem statement.

KNOWN     live data, fetched recently, and directly says what we report
PROBABLE  inferred (web reports, AI estimate, institution that is normally 24x7, OSM has no entry)
OUTDATED  cached or sample data older than the freshness window
UNKNOWN   no data at all; the app says so instead of inventing an answer
"""
from datetime import datetime, timezone

KNOWN = "KNOWN"
PROBABLE = "PROBABLE"
OUTDATED = "OUTDATED"
UNKNOWN = "UNKNOWN"

ORDER = [KNOWN, PROBABLE, OUTDATED, UNKNOWN]


def age_minutes(fetched_at, now=None):
    if fetched_at is None:
        return None
    if isinstance(fetched_at, str):
        fetched_at = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    now = now or datetime.now(timezone.utc)
    return (now - fetched_at).total_seconds() / 60.0


def source_label(source, fetched_at, fresh_minutes=15, now=None):
    """Label for a piece of data based on where it came from and how old it is."""
    if source is None:
        return UNKNOWN
    if source == "mock":
        return OUTDATED
    if source == "inferred":
        return PROBABLE
    age = age_minutes(fetched_at, now)
    if age is None:
        return UNKNOWN
    return KNOWN if age <= fresh_minutes else OUTDATED


def worst(labels):
    labels = [l for l in labels if l]
    if not labels:
        return UNKNOWN
    return max(labels, key=ORDER.index)
