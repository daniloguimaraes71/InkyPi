import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_wikipedia_image
from utils.app_utils import get_font
from utils.design_variants import get_variant
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

NIGHT_IMAGES = {
    "spring": "Moon",
    "summer": "Milky_Way",
    "autumn": "Moon",
    "winter": "Aurora",
}

POEMS = {
    "spring": [
        "春の夜の\n夢ばかりなる\n手枕に",
        "月影に\n包まれて\n眠る夜",
        "花びらが\n風に舞い\n静寂の中",
    ],
    "summer": [
        "星空の\n下で聞く\n虫の声",
        "涼風に\n包まれて\n夏の夜",
        "蛍火が\n暗闇を\n照らす時",
    ],
    "autumn": [
        "秋の夜の\n月明かりに\n照らされて",
        "紅葉の\n散る中で\n眠りにつく",
        "虫の声\n遠く聞こえる\n秋の夜",
    ],
    "winter": [
        "雪の夜の\n静寂に\n包まれて",
        "冬の月\n冷たく光る\n夜空に",
        "星の光\n導くままに\n安らかに",
    ],
}


class GoodnightCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        v = get_variant(settings.get("designStyle"))
        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        image_keyword = NIGHT_IMAGES.get(season, "Moon")
        night_image = get_wikipedia_image(image_keyword, (300, 300))

        image_data_uri = self.image_to_data_uri(night_image)

        seed = now.year * 10000 + now.month * 100 + now.day
        poems = POEMS.get(season, POEMS["spring"])
        poem = poems[seed % len(poems)]

        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]

            template_params = {
                "palette": palette,
                "season_info": season_info,
                "now": now,
                "poem": poem,
                "night_image": image_data_uri,
                "plugin_settings": settings,
            }

            image = self.render_image(dimensions_for_render, "goodnight_card.html", "goodnight_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, settings, poem, night_image, v)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, settings, poem, night_image, v):
        """Minimalist dark night card with centered poem."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg_dark'])
        draw = ImageDraw.Draw(img)

        f_greeting = get_font(v.heading_font, int(w * 0.04))
        f_poem = get_font(v.heading_font, int(w * 0.028))
        f_ms = get_font(v.heading_font, int(w * 0.016))
        f_ms_en = get_font(v.body_font, int(w * 0.012))

        moon_x = w // 2
        moon_y = int(h * 0.2)
        moon_r = int(w * 0.04)
        for r in range(moon_r + 8, moon_r - 2, -2):
            alpha = int(40 * (1 - (r - moon_r) / 10))
            draw.ellipse([moon_x - r, moon_y - r, moon_x + r, moon_y + r], fill=(30, 30, 50))
        draw.ellipse([moon_x - moon_r, moon_y - moon_r, moon_x + moon_r, moon_y + moon_r], fill='#E0D8C0')
        draw.ellipse([moon_x - moon_r + 12, moon_y - moon_r + 4, moon_x + moon_r - 4, moon_y + moon_r - 4], fill=C['bg_dark'])

        gy = int(h * 0.38)
        bbox = draw.textbbox((0, 0), "おやすみなさい", font=f_greeting)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, gy), "おやすみなさい", font=f_greeting, fill='#E0D8C0')

        poem_lines = poem.split('\n')
        py = gy + int(h * 0.08 * sm)
        for line in poem_lines:
            bbox = draw.textbbox((0, 0), line, font=f_poem)
            tw = bbox[2] - bbox[0]
            draw.text(((w - tw) // 2, py), line, font=f_poem, fill=C['text_secondary'])
            py += int(h * 0.055 * sm)

        if season_info:
            ms_x = w - int(w * 0.05)
            ms_y = h - int(h * 0.055 * sm)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill=C['accent'])
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.022 * sm)), e, font=f_ms_en, fill=C['text_light'])

        return img
