import logging
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_wikipedia_image
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Night-related Wikipedia images
NIGHT_IMAGES = {
    "spring": "Moon",
    "summer": "Milky_Way",
    "autumn": "Moon",
    "winter": "Aurora",
}

# Seasonal poems
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

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

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

        # Get night image
        image_keyword = NIGHT_IMAGES.get(season, "Moon")
        night_image = get_wikipedia_image(image_keyword, (300, 300))
        
        # Save image to static directory for HTML rendering
        image_url = None
        if night_image:
            import os
            static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'images', 'cache')
            os.makedirs(static_dir, exist_ok=True)
            image_path = os.path.join(static_dir, 'night_image.png')
            night_image.save(image_path, 'PNG')
            image_url = f'/static/images/cache/night_image.png'

        # Pick poem based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        poems = POEMS.get(season, POEMS["spring"])
        poem = poems[seed % len(poems)]

        # Try HTML render
        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "now": now,
                "poem": poem,
                "night_image": image_url,
            }
            
            image = self.render_image(dimensions_for_render, "goodnight_card.html", "goodnight_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL
        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, settings, poem, night_image)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, settings, poem, night_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Dark background for night
        img = Image.new('RGB', (w, h), '#1A1A2E')
        draw = ImageDraw.Draw(img)

        font_greeting = get_font("Noto Serif JP", int(w * 0.1))
        font_poem = get_font("Noto Serif JP", int(w * 0.04))
        font_small = get_font("Noto Sans JP", int(w * 0.025))

        # Night image
        if night_image:
            img_x, img_y = int(w * 0.6), int(h * 0.15)
            img_w, img_h = int(w * 0.35), int(h * 0.6)
            photo_resized = night_image.resize((img_w, img_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (img_x, img_y))
            draw = ImageDraw.Draw(img)
            draw.rectangle([img_x-1, img_y-1, img_x+img_w+1, img_y+img_h+1], outline='#3A3A4E', width=1)

        # Greeting
        draw.text((int(w * 0.08), int(h * 0.35)), "おやすみなさい", font=font_greeting, fill='#E0D8C0', anchor="mm")
        draw.text((int(w * 0.08), int(h * 0.45)), "Good Night", font=font_small, fill='#B0A890', anchor="mm")

        # Poem
        poem_lines = poem.split('\n')
        poem_y = int(h * 0.55)
        for line in poem_lines:
            draw.text((int(w * 0.08), poem_y), line, font=font_poem, fill='#B0A890')
            poem_y += int(h * 0.06)

        # Micro-season
        if season_info:
            draw.text((int(w * 0.08), int(h * 0.9)), f"時候: {season_info['micro_season']['kanji']}", font=font_small, fill='#807860')

        return img
