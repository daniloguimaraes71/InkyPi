import logging
import random
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Curated Kansai events by season with more detail
EVENTS = {
    "spring": [
        {"name": "お花見ピクニック", "location": "大阪城公園", "type": "花見", "desc": "Cherry blossom viewing picnic"},
        {"name": "奈良公園の鹿と散歩", "location": "奈良", "type": "アウトドア", "desc": "Walk with deer in Nara Park"},
        {"name": "清水寺と祇園散策", "location": "京都", "type": "観光", "desc": "Kiyomizdera & Gion walk"},
        {"name": "箕面の滝ハイキング", "location": "箕面", "type": "ハイキング", "desc": "Minoh waterfall hike"},
    ],
    "summer": [
        {"name": "天神祭りの花火", "location": "大阪", "type": "祭り", "desc": "Tenjin Matsuri fireworks"},
        {"name": "須磨海水浴場", "location": "神戸", "type": "ビーチ", "desc": "Suma Beach day"},
        {"name": "有馬温泉でリフレッシュ", "location": "神戸", "type": "温泉", "desc": "Arima Onsen refresh"},
        {"name": "梅田スカイビルの夜景", "location": "大阪", "type": "観光", "desc": "Umeda Sky Building night view"},
    ],
    "autumn": [
        {"name": "紅葉狩り", "location": "京都", "type": "紅葉", "desc": "Autumn leaf viewing"},
        {"name": "伏見稲荷大社", "location": "京都", "type": "観光", "desc": "Fushimi Inari shrine"},
        {"name": "神戸ルミナリー", "location": "神戸", "type": "イベント", "desc": "Kobe Luminarie"},
        {"name": "姫路城と日本庭園", "location": "姫路", "type": "観光", "desc": "Himeji Castle & garden"},
    ],
    "winter": [
        {"name": "奈良のイルミネーション", "location": "奈良", "type": "イルミネーション", "desc": "Nara illumination"},
        {"name": "大阪クリスマスマーケット", "location": "大阪", "type": "マーケット", "desc": "Osaka Christmas Market"},
        {"name": "神戸の光のルナリエ", "location": "神戸", "type": "イルミネーション", "desc": "Kobe Luminarie"},
        {"name": "有馬温泉日帰り旅行", "location": "有馬", "type": "温泉", "desc": "Arima Onsen day trip"},
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
        
        # Elegant background
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", "#FAFAF8"), "RGB")
        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", "#2C2C2C"), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#8B7355"), "RGB")
        secondary = ImageColor.getcolor(palette.get("secondary", "#C4B99C"), "RGB")

        # Fonts
        font_title = get_font("Noto Serif JP", int(w * 0.06))
        font_subtitle = get_font("Noto Sans JP", int(w * 0.035))
        font_event_name = get_font("Noto Serif JP", int(w * 0.045))
        font_event_desc = get_font("Noto Sans JP", int(w * 0.03))
        font_location = get_font("Noto Sans JP", int(w * 0.028))
        font_small = get_font("Noto Sans JP", int(w * 0.025))

        # Header
        left_x = int(w * 0.08)
        
        # Title - Japanese with English subtitle
        draw.text((left_x, int(h * 0.08)), "週末のおでかけ", font=font_title, fill=primary)
        
        # Weekend date
        weekend_end = weekend_start + timedelta(days=1)
        date_str = f"{weekend_start.strftime('%m月%d日')} - {weekend_end.strftime('%m月%d日')}"
        draw.text((left_x, int(h * 0.16)), date_str, font=font_subtitle, fill=primary + (180,))

        # Subtle divider
        draw.line([(left_x, int(h * 0.22)), (w - left_x, int(h * 0.22))], fill=secondary + (80,), width=1)

        # Events list - elegant layout
        y = int(h * 0.28)
        for i, event in enumerate(events):
            # Event number - subtle circle
            circle_x = left_x + int(w * 0.02)
            circle_y = y + int(h * 0.02)
            draw.ellipse([circle_x - 8, circle_y - 8, circle_x + 8, circle_y + 8], fill=accent + (60,))
            draw.text((circle_x, circle_y), str(i + 1), font=font_small, fill=accent, anchor="mm")
            
            # Event name
            draw.text((left_x + int(w * 0.06), y), event["name"], font=font_event_name, fill=primary)
            
            # Location and type
            loc_text = f"{event['location']} · {event['type']}"
            draw.text((left_x + int(w * 0.06), y + int(h * 0.04)), loc_text, font=font_location, fill=primary + (150,))
            
            # English description
            draw.text((left_x + int(w * 0.06), y + int(h * 0.07)), event["desc"], font=font_event_desc, fill=primary + (120,))
            
            y += int(h * 0.18)

        # Footer - Season context
        footer_y = int(h * 0.88)
        draw.line([(left_x, footer_y), (w - left_x, footer_y)], fill=secondary + (60,), width=1)
        
        # Date
        date_str = now.strftime("%Y年%m月%d日")
        draw.text((left_x, footer_y + int(h * 0.03)), date_str, font=font_small, fill=primary + (150,))
        
        # Micro-season with context
        if season_info:
            season_label = f"時候: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            draw.text((w - left_x, footer_y + int(h * 0.03)), season_label, font=font_small, fill=accent, anchor="rt")
            draw.text((w - left_x, footer_y + int(h * 0.07)), season_meaning, font=font_small, fill=primary + (120,), anchor="rt")

        return img
