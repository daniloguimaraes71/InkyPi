import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

FLOWERS = [
    {"ja": "桜", "en": "Cherry Blossom", "kotoba": "spiritual beauty", "season": "spring"},
    {"ja": "梅", "en": "Plum Blossom", "kotoba": "patience", "season": "spring"},
    {"ja": "藤", "en": "Wisteria", "kotoba": "welcome", "season": "spring"},
    {"ja": "紫陽花", "en": "Hydrangea", "kotoba": "heartfelt emotions", "season": "summer"},
    {"ja": "蓮", "en": "Lotus", "kotoba": "purity", "season": "summer"},
    {"ja": "向日葵", "en": "Sunflower", "kotoba": "adoration", "season": "summer"},
    {"ja": "萩", "en": "Bush Clover", "kotoba": "thoughtfulness", "season": "autumn"},
    {"ja": "菊", "en": "Chrysanthemum", "kotoba": "nobility", "season": "autumn"},
    {"ja": "紅葉", "en": "Maple", "kotoba": "grace", "season": "autumn"},
    {"ja": "椿", "en": "Camellia", "kotoba": "admiration", "season": "winter"},
    {"ja": "水仙", "en": "Daffodil", "kotoba": "self-love", "season": "winter"},
    {"ja": "梅", "en": "Winter Plum", "kotoba": "perseverance", "season": "winter"},
]

MOODS = [
    {"ja": "今日は自分を大切にする日", "en": "Today, take care of yourself", "emoji": "🌿"},
    {"ja": "深呼吸して、リラックス", "en": "Take a deep breath and relax", "emoji": "🍃"},
    {"ja": "小さな幸せを見つけて", "en": "Find small moments of joy", "emoji": "✨"},
    {"ja": "季節の移ろいを感じて", "en": "Feel the changing of seasons", "emoji": "🌸"},
    {"ja": "お茶を一杯、ゆっくりと", "en": "A cup of tea, slowly", "emoji": "🍵"},
    {"ja": "今日も一日お疲れ様", "en": "Well done for today", "emoji": "🌙"},
]


class MoodCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        # Pick flower and mood based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)

        # Filter flowers by current season
        month = now.month
        if month in [3, 4, 5]:
            current_season = "spring"
        elif month in [6, 7, 8]:
            current_season = "summer"
        elif month in [9, 10, 11]:
            current_season = "autumn"
        else:
            current_season = "winter"

        seasonal_flowers = [f for f in FLOWERS if f["season"] == current_season]
        flower = random.choice(seasonal_flowers) if seasonal_flowers else random.choice(FLOWERS)
        mood = random.choice(MOODS)
        random.seed()

        return self._draw_card(dimensions, flower, mood, season_info, palette, settings, now)

    def _draw_card(self, dimensions, flower, mood, season_info, palette, settings, now):
        w, h = dimensions
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", palette.get("bg", "#F8F5F0")), "RGB")

        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", palette.get("primary", "#333333")), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#888888"), "RGB")
        secondary_color = ImageColor.getcolor(palette.get("secondary", "#AAAAAA"), "RGB")

        font_large = get_font("Noto Serif JP", int(w * 0.12))
        font_medium = get_font("Noto Serif JP", int(w * 0.05))
        font_small = get_font("Noto Sans JP", int(w * 0.035))
        font_tiny = get_font("Noto Sans JP", int(w * 0.025))

        # Large flower kanji centered
        draw.text((w / 2, h * 0.3), flower["ja"], font=font_large, fill=primary, anchor="mm")

        # English name
        draw.text((w / 2, h * 0.42), flower["en"], font=font_medium, fill=primary + (180,), anchor="mm")

        # 花言葉 (flower language)
        kotoba_label = f"花言葉: {flower['kotoba']}"
        draw.text((w / 2, h * 0.50), kotoba_label, font=font_small, fill=accent, anchor="mm")

        # Divider
        draw.line([(w * 0.2, h * 0.57), (w * 0.8, h * 0.57)], fill=accent + (60,), width=1)

        # Mood message
        draw.text((w / 2, h * 0.65), mood["ja"], font=font_medium, fill=primary, anchor="mm")
        draw.text((w / 2, h * 0.72), mood["en"], font=font_small, fill=primary + (150,), anchor="mm")

        # Footer: date and micro-season
        date_str = now.strftime("%B %d")
        draw.text((w * 0.08, h * 0.90), date_str, font=font_tiny, fill=primary + (120,))

        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            draw.text((w * 0.92, h * 0.90), season_label, font=font_tiny, fill=accent + (180,), anchor="rt")

        return img
