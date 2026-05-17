import json
import os
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "micro_seasons.json")
_cache = None


def _load_data():
    global _cache
    if _cache is None:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def get_current_micro_season(today=None):
    if today is None:
        today = date.today()
    elif isinstance(today, datetime):
        today = today.date()

    data = _load_data()
    month = today.month
    day = today.day

    for ms in data["micro_seasons"]:
        ms_month = ms["month"]
        day_start = ms["day_start"]
        day_end = ms["day_end"]

        # Handle wrapping across months (e.g., month 1 day 30 -> month 2 day 3)
        if ms_month == month:
            if day_start <= day_end:
                if day_start <= day <= day_end:
                    return ms
            else:
                # Wraps into next month
                if day >= day_start:
                    return ms
        # Check if we're in the wrapped portion (next month)
        elif ms_month == (month - 1 if month > 1 else 12):
            if day_start > day_end:
                if day <= day_end:
                    return ms

    # Fallback: find closest by date comparison
    best = None
    best_dist = 999
    for ms in data["micro_seasons"]:
        ms_date = date(today.year, ms["month"], min(ms["day_start"], 28))
        dist = abs((today - ms_date).days)
        if dist < best_dist:
            best_dist = dist
            best = ms
    return best


def get_solar_term_for_micro_season(ms):
    data = _load_data()
    for st in data["solar_terms"]:
        if st["name"] == ms["solar_term"]:
            return st
    return None


def get_current_solar_term(today=None):
    ms = get_current_micro_season(today)
    if ms:
        return get_solar_term_for_micro_season(ms)
    return None


def get_seasonal_palette(today=None):
    st = get_current_solar_term(today)
    if st and "palette" in st:
        return st["palette"]
    return {
        "primary": "#333333",
        "secondary": "#888888",
        "accent": "#666666",
        "bg": "#F5F5F5"
    }


def get_micro_season_label(today=None):
    ms = get_current_micro_season(today)
    if not ms:
        return ""
    return f"{ms['kanji']}（{ms['english']}）"


def get_full_season_info(today=None):
    ms = get_current_micro_season(today)
    if not ms:
        return None
    st = get_solar_term_for_micro_season(ms)
    palette = get_seasonal_palette(today)
    return {
        "micro_season": ms,
        "solar_term": st,
        "palette": palette,
        "label": f"{ms['kanji']}（{ms['english']}）",
        "solar_term_label": f"{st['name']} {st['english']}" if st else ""
    }
