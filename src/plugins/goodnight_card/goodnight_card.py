import logging
import math
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class GoodnightCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        return self._draw_card(dimensions, now, season_info, palette, settings)

    def _draw_card(self, dimensions, now, season_info, palette, settings):
        w, h = dimensions
        
        # Elegant dark background for night
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", "#1A1A2E"), "RGB")
        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", "#E0D8C0"), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#8B7355"), "RGB")
        secondary = ImageColor.getcolor(palette.get("secondary", "#C4B99C"), "RGB")

        # Fonts
        font_greeting = get_font("Noto Serif JP", int(w * 0.1))
        font_subtitle = get_font("Noto Sans JP", int(w * 0.04))
        font_poem = get_font("Noto Serif JP", int(w * 0.035))
        font_small = get_font("Noto Sans JP", int(w * 0.028))

        # Center - Moon
        center_x = int(w * 0.35)
        center_y = int(h * 0.35)
        radius = int(min(w, h) * 0.12)
        
        # Draw moon - elegant crescent
        self._draw_moon(draw, center_x, center_y, radius, now)

        # Greeting - elegant Japanese
        draw.text((center_x, int(h * 0.58)), "おやすみなさい", font=font_greeting, fill=primary, anchor="mm")
        draw.text((center_x, int(h * 0.66)), "Good Night", font=font_subtitle, fill=primary + (180,), anchor="mm")

        # Right side - Poetic message
        right_x = int(w * 0.62)
        
        # Seasonal poem or message
        poems = [
            "月影に 包まれて 眠る夜",
            "静寂の 夜に溶けて ゆく夢",
            "星の光 導くままに 安らかに",
            "夜の帳 降りる中で 息を整え",
        ]
        
        seed = now.year * 10000 + now.month * 100 + now.day
        poem_idx = seed % len(poems)
        draw.text((right_x, int(h * 0.35)), poems[poem_idx], font=font_poem, fill=primary + (150,))

        # Footer - Season context
        footer_y = int(h * 0.85)
        left_x = int(w * 0.08)
        draw.line([(left_x, footer_y), (w - left_x, footer_y)], fill=secondary + (40,), width=1)
        
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

    def _draw_moon(self, draw, cx, cy, radius, now):
        # Elegant crescent moon
        moon_color = (240, 230, 200, 255)
        shadow_color = (30, 30, 50, 255)

        # Full moon circle
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=moon_color
        )

        # Shadow overlay for crescent effect
        phase = (now.day % 30) / 30.0
        offset = radius * (1 - 2 * phase)
        shadow_radius = int(radius * 1.05)

        draw.ellipse(
            [cx + offset - shadow_radius, cy - shadow_radius,
             cx + offset + shadow_radius, cy + shadow_radius],
            fill=shadow_color
        )
