import logging
import math
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.card_design import CardDesign
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class GoodnightCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        return self._draw_card(dimensions, orientation, now, season_info, palette, settings)

    def _draw_card(self, dimensions, orientation, now, season_info, palette, settings):
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Initialize design system
        design = CardDesign((w, h), orientation)
        
        # Create base card with dark background
        img = design.create_base_card(bg_color='#1A1A2E', palette=palette)
        draw = ImageDraw.Draw(img)

        # Override colors for dark theme
        primary_color = '#E0D8C0'
        secondary_color = '#8B7355'

        # Center - Moon
        center_x = int(w * 0.35)
        center_y = int(h * 0.35)
        radius = int(min(w, h) * 0.12)
        
        # Draw moon - elegant crescent
        self._draw_moon(draw, center_x, center_y, radius, now)

        # Greeting - elegant Japanese
        draw.text((center_x, int(h * 0.58)), "おやすみなさい", font=design.fonts['display'], 
                 fill=primary_color, anchor="mm")
        draw.text((center_x, int(h * 0.66)), "Good Night", font=design.fonts['body'], 
                 fill=primary_color + 'B0', anchor="mm")

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
        draw.text((right_x, int(h * 0.35)), poems[poem_idx], font=design.fonts['caption'], 
                 fill=primary_color + '99')

        # Footer
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info)

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
        offset = int(radius * (1 - 2 * phase))
        shadow_radius = int(radius * 1.05)

        draw.ellipse(
            [cx + offset - shadow_radius, cy - shadow_radius,
             cx + offset + shadow_radius, cy + shadow_radius],
            fill=shadow_color
        )
