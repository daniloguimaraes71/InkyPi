"""
Kansai Events News Fetcher
Fetches current tourism events and activities from the Kansai region of Japan.
"""

import logging
import requests
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup
from utils.http_client import get_http_session

logger = logging.getLogger(__name__)

# Tourism and event-focused RSS feeds for Kansai region
NEWS_SOURCES = [
    {
        "name": "Google News - Kansai Events",
        "url": "https://news.google.com/rss/search?q=関西+おでかけ+イベント+2026&hl=ja&gl=JP&ceid=JP:ja",
        "type": "rss",
        "headers": {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
    },
    {
        "name": "Google News - Kyoto Events",
        "url": "https://news.google.com/rss/search?q=京都+イベント+観光&hl=ja&gl=JP&ceid=JP:ja",
        "type": "rss",
        "headers": {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
    },
    {
        "name": "Google News - Osaka Events",
        "url": "https://news.google.com/rss/search?q=大阪+イベント+観光&hl=ja&gl=JP&ceid=JP:ja",
        "type": "rss",
        "headers": {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
    },
]

# Event-related keywords to filter news
EVENT_KEYWORDS = [
    "祭り", "イベント", "観光", "展示", "展覧会", "フェス", "音楽", "花火",
    "桜", "紅葉", "イルミネーション", "マーケット", "温泉", "ハイキング",
    "散歩", "ピクニック", "ビーチ", "寺", "神社", "城", "庭園",
    "festival", "event", "exhibition", "tourism", "market", "concert",
]

# Backup curated events if news fetch fails
BACKUP_EVENTS = {
    "spring": [
        {"name": "お花見ピクニック", "location": "大阪城公園", "type": "花見", "desc": "Cherry blossom viewing picnic", "wiki": "大阪城"},
        {"name": "奈良公園の鹿と散歩", "location": "奈良", "type": "アウトドア", "desc": "Walk with deer in Nara Park", "wiki": "奈良公園"},
        {"name": "清水寺と祇園散策", "location": "京都", "type": "観光", "desc": "Kiyomizdera & Gion walk", "wiki": "清水寺"},
    ],
    "summer": [
        {"name": "天神祭りの花火", "location": "大阪", "type": "祭り", "desc": "Tenjin Matsuri fireworks", "wiki": "天神祭"},
        {"name": "須磨海水浴場", "location": "神戸", "type": "ビーチ", "desc": "Suma Beach day", "wiki": "須磨海水浴場"},
        {"name": "有馬温泉でリフレッシュ", "location": "神戸", "type": "温泉", "desc": "Arima Onsen refresh", "wiki": "有馬温泉"},
    ],
    "autumn": [
        {"name": "紅葉狩り", "location": "京都", "type": "紅葉", "desc": "Autumn leaf viewing", "wiki": "京都"},
        {"name": "伏見稲荷大社", "location": "京都", "type": "観光", "desc": "Fushimi Inari shrine", "wiki": "伏見稲荷大社"},
        {"name": "神戸ルミナリー", "location": "神戸", "type": "イベント", "desc": "Kobe Luminarie", "wiki": "神戸ルミナリー"},
    ],
    "winter": [
        {"name": "奈良のイルミネーション", "location": "奈良", "type": "イルミネーション", "desc": "Nara illumination", "wiki": "奈良公園"},
        {"name": "大阪クリスマスマーケット", "location": "大阪", "type": "マーケット", "desc": "Osaka Christmas Market", "wiki": "大阪"},
        {"name": "有馬温泉日帰り旅行", "location": "有馬", "type": "温泉", "desc": "Arima Onsen day trip", "wiki": "有馬温泉"},
    ],
}

KANSAI_LOCATIONS = ["大阪", "京都", "神戸", "奈良", "滋賀", "和歌山", "関西", "近畿"]


def fetch_kansai_events():
    """
    Fetch current tourism and event news from Kansai region.
    Returns a list of event dicts.
    """
    events = []
    session = get_http_session()
    
    for source in NEWS_SOURCES:
        try:
            if source["type"] == "rss":
                headers = source.get("headers", {})
                resp = session.get(source["url"], timeout=10, headers=headers)
                if resp.status_code == 200:
                    parsed = parse_rss(resp.text, source["name"])
                    events.extend(parsed)
        except Exception as e:
            logger.warning(f"Failed to fetch from {source['name']}: {e}")
    
    # Google News search already filters for Kansai events
    # Deduplicate by title prefix (first 30 chars)
    seen = set()
    kansai_events = []
    for event in events:
        title = event.get("name", "")
        # Use first 30 chars as dedup key
        title_key = title[:30]
        if title_key not in seen:
            seen.add(title_key)
            # Try to extract location from title/desc
            text = title + " " + event.get("desc", "")
            for loc in KANSAI_LOCATIONS:
                if loc in text:
                    event["wiki"] = loc
                    break
            if "wiki" not in event:
                event["wiki"] = "関西"
            kansai_events.append(event)
    
    return kansai_events


def parse_rss(xml_text, source_name):
    """Parse RSS XML and extract news items."""
    items = []
    try:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_text)
        
        # RSS 2.0 format
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                source = item.findtext("source", "")
                
                # Extract subtitle from title by removing source suffix and brackets
                subtitle = _extract_subtitle(title, source)
                
                items.append({
                    "name": title,
                    "desc": subtitle,
                    "location": "",
                    "type": "イベント",
                    "link": link,
                    "source": source_name,
                })
    except Exception as e:
        logger.warning(f"Failed to parse RSS from {source_name}: {e}")
    
    return items


def _extract_subtitle(title, source=""):
    """Extract a meaningful short subtitle from a Google News title."""
    import re
    clean = title
    if source and source in clean:
        clean = clean.replace(f" - {source}", "").replace(f" {source}", "")
    elif " - " in clean:
        parts = clean.rsplit(" - ", 1)
        clean = parts[0]
    clean = re.sub(r'^【[^】]*】\s*', '', clean)
    
    # Extract the key descriptive part after the date/number prefix
    # Remove leading date patterns like "2026年5月16日・17日"
    clean = re.sub(r'^\d{4}年\d{1,2}月\d{1,2}日[・〜]?\d{1,2}日?\s*', '', clean)
    
    # Truncate to reasonable subtitle length
    if len(clean) > 30:
        clean = clean[:29] + "…"
    
    return clean if len(clean) > 3 else title


def get_kansai_events_list(now, count=3):
    """
    Get current Kansai events list, either from news or backup.
    Returns a list of event dicts.
    """
    # Determine season
    month = now.month
    if month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    elif month in [9, 10, 11]:
        season = "autumn"
    else:
        season = "winter"
    
    # Try to fetch live news
    try:
        news_events = fetch_kansai_events()
        if news_events:
            # Pick count events based on date
            seed = now.year * 10000 + now.month * 100 + now.day
            random.seed(seed)
            selected = random.sample(news_events, min(count, len(news_events)))
            random.seed()
            logger.info(f"Using {len(selected)} live events")
            return selected
    except Exception as e:
        logger.warning(f"Failed to fetch live events, using backup: {e}")
    
    # Fallback to curated events
    seed = now.year * 10000 + now.month * 100 + now.day
    random.seed(seed)
    events = BACKUP_EVENTS.get(season, BACKUP_EVENTS["spring"])
    selected = random.sample(events, min(count, len(events)))
    random.seed()
    logger.info(f"Using {len(selected)} backup events")
    return selected


def get_kansai_events(now):
    """
    Get a single Kansai event (for backwards compatibility).
    Returns an event dict.
    """
    events = get_kansai_events_list(now, count=1)
    return events[0] if events else None
