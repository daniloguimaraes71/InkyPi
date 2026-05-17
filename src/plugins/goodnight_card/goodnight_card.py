import logging
import math
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info
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
        palette = season_info["palette"] if season_info else {
            "primary": "#333333", "secondary": "#888888", "accent": "#666666", "bg": "#F5F5F5"
        }

        return self._draw_card(dimensions, now, season_info, palette, settings)

    def _draw_card(self, dimensions, now, season_info, palette, settings):
        w, h = dimensions
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", palette.get("bg", "#1a1a2e")), "RGB")

        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", palette.get("primary", "#e0d8c0")), "RGB")

        # Moon
        cx, cy = w * 0.5, h * 0.35
        radius = min(w, h) * 0.15
        self._draw_moon(draw, cx, cy, radius, now)

        # Goodnight text
        font_large = get_font("Noto Serif JP", int(w * 0.08))
        font_small = get_font("Noto Serif JP", int(w * 0.04))

        # Japanese text
        text_y = h * 0.62
        draw.text((w / 2, text_y), "おやすみなさい", font=font_large, fill=primary, anchor="mm")

        # English subtitle
        draw.text((w / 2, text_y + w * 0.07), "Good Night", font=font_small, fill=primary + (180,), anchor="mm")

        # Date
        date_str = now.strftime("%A, %B %d")
        draw.text((w / 2, h * 0.82), date_str, font=font_small, fill=primary + (150,), anchor="mm")

        # Micro-season footer
        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            font_tiny = get_font("Noto Serif JP", int(w * 0.03))
            draw.text((w / 2, h * 0.92), season_label, font=font_tiny, fill=primary + (120,), anchor="mm")

        return img

    def _draw_moon(self, draw, cx, cy, radius, now):
        # Simple waxing crescent moon
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
        shadow_radius = radius * 1.05

        draw.ellipse(
            [cx + offset - shadow_radius, cy - shadow_radius,
             cx + offset + shadow_radius, cy + shadow_radius],
            fill=shadow_color
        )
