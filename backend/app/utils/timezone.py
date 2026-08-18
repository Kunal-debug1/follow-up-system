"""
Centralised timezone helpers.

Strategy:
    - Database stores UTC timestamps
    - Backend uses timezone-aware datetime (UTC)
    - "Business day" (today) is calculated in CRM_TIMEZONE (default Asia/Kolkata)
      because the CRM serves an India-based operation.

Only use these helpers for business-day comparisons.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo(os.getenv("CRM_TIMEZONE", "Asia/Kolkata"))


def business_today() -> date:
    """Return today's date in the configured business timezone."""
    return datetime.now(BUSINESS_TZ).date()


def business_today_iso() -> str:
    """Return today's date in the configured business timezone as ISO string."""
    return business_today().isoformat()


def business_start_of_day() -> datetime:
    """Return the start of today (00:00:00) as a tz-aware UTC datetime."""
    today_local = datetime.combine(business_today(), time.min, tzinfo=BUSINESS_TZ)
    return today_local.astimezone(timezone.utc)


def business_end_of_day() -> datetime:
    """Return the start of tomorrow (00:00:00 local) as a tz-aware UTC datetime."""
    tomorrow_local = datetime.combine(
        business_today() + timedelta(days=1), time.min, tzinfo=BUSINESS_TZ
    )
    return tomorrow_local.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)