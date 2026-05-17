import logging
import random
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Curated Kansai events and activities by season
EVENTS = {
    "spring": [
        {"name": " cherry blossom viewing", "location": "Osaka Castle Park", "type": "花見"},
        {"name": "Nara Park picnic", "location": "Nara", "type": "アウトドア"},
        {"name": "Kyoto temple visit", "location": "Kyoto", "type": "観光"},
        {"name": "Minoh waterfall hike", "location": "Minoh", "type": "ハイキング"},
    ],
    "summer": [
        {"name": "Tenjin Matsuri", "location": "Osaka", "type": "祭り"},
        {"name": "Suma Beach", "location": "Kobe", "type": "ビーチ"},
        {"name": "Arima Onsen", "location": "Kobe", "type": "温泉"},
        {"name": "Umeda Sky Building", "location": "Osaka", "type": "観光"},
    ],
    "autumn": [
        {"name": "Momiji viewing", "location": "Kyoto", "type": "紅葉"},
        {"name": "Fushimi Inari", "location": "Kyoto", "type": "観光"},
        {"name": "Kobe Luminarie", "location": "Kobe", "type": "イベント"},
        {"name": "Himeji Castle", "location": "Himeji", "type": "観光"},
    ],
    "winter": [
        {"name": "Nara illumination", "location": "Nara", "type": "イルミネーション"},
        {"name": "Osaka Christmas Market", "location": "Osaka", "type": "マーケット"},
        {"name": "Kobe illumination", "location": "Kobe", "type": "イルミネーション"},
        {"name": "Hot spring day trip", "location": "Arima", "type": "温泉"},
    ],
}


class KansaiEvents(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        # Determine current season
        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        # Pick events based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        events = random.sample(EVENTS.get(season, []), min(3, len(EVENTS.get(season, []))))
        random.seed()

        # Find next weekend
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            days_until_saturday = 0
        weekend_start = now.date() + timedelta(days=days_until_saturday)

        return self._draw_card(dimensions, events, season_info, palette, settings, now, weekend_start, season)

    def _draw_card(self, dimensions, events, season_info, palette, settings, now, weekend_start, season):
        w, h = dimensions
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", palette.get("bg", "#F8F5F0")), "RGB")

        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", palette.get("primary", "#333333")), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#888888"), "RGB")

        font_title = get_font("Noto Serif JP", int(w * 0.06))
        font_event = get_font("Noto Sans JP", int(w * 0.04))
        font_small = get_font("Noto Sans JP", int(w * 0.03))

        # Header
        draw.text((w * 0.08, h * 0.06), "週末の関西", font=font_title, fill=primary)
        draw.text((w * 0.08, h * 0.13), f"Weekend in Kansai · {season.title()}", font=font_small, fill=primary + (150,))

        # Weekend date
        weekend_end = weekend_start + timedelta(days=1)
        date_str = f"{weekend_start.strftime('%b %d')} - {weekend_end.strftime('%b %d')}"
        draw.text((w * 0.08, h * 0.20), date_str, font=font_small, fill=accent)

        # Divider
        draw.line([(w * 0.08, h * 0.26), (w * 0.92, h * 0.26)], fill=accent + (60,), width=1)

        # Events list
        y = h * 0.30
        for event in events:
            draw.text((w * 0.08, y), event["name"], font=font_event, fill=primary)
            draw.text((w * 0.08, y + w * 0.035), f"{event['location']} · {event['type']}", font=font_small, fill=primary + (150,))
            y += h * 0.15

        # Footer with micro-season
        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            draw.text((w * 0.92, h * 0.92), season_label, font=font_small, fill=accent + (180,), anchor="rt")

        return img
