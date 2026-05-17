import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_seasonal_flower_image
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Seasonal flowers with 花言葉 (flower language)
FLOWERS = {
    "spring": [
        {"ja": "桜", "en": "Cherry Blossom", "kotoba": "spiritual beauty", "poem": "散る桜 残る桜も 散る桜"},
        {"ja": "梅", "en": "Plum Blossom", "kotoba": "patience", "poem": "梅が香に のっとひかるる 月影か"},
        {"ja": "藤", "en": "Wisteria", "kotoba": "welcome", "poem": "藤波の 花のしたなる 泉水"},
        {"ja": "菜の花", "en": "Rapeseed Blossom", "kotoba": "vitality", "poem": "菜の花や 月は東に 日は西に"},
    ],
    "summer": [
        {"ja": "紫陽花", "en": "Hydrangea", "kotoba": "heartfelt emotions", "poem": "紫陽花や 今日の面影は なき人の"},
        {"ja": "蓮", "en": "Lotus", "kotoba": "purity", "poem": "蓮の花 開くばかりの 池水か"},
        {"ja": "向日葵", "en": "Sunflower", "kotoba": "adoration", "poem": "向日葵の 日にむかひけり 暑さの中"},
        {"ja": "朝顔", "en": "Morning Glory", "kotoba": "transience", "poem": "朝顔に つるべとられて 貰ひ水"},
    ],
    "autumn": [
        {"ja": "萩", "en": "Bush Clover", "kotoba": "thoughtfulness", "poem": "萩の花 尾花が末の 秋風"},
        {"ja": "菊", "en": "Chrysanthemum", "kotoba": "nobility", "poem": "菊の香や 奈良には古き 仏たち"},
        {"ja": "紅葉", "en": "Maple", "kotoba": "grace", "poem": "紅葉して 松の緑の 若葉かな"},
        {"ja": "秋桜", "en": "Cosmos", "kotoba": "harmony", "poem": "秋桜 のびた茎の 花が揺れ"},
    ],
    "winter": [
        {"ja": "椿", "en": "Camellia", "kotoba": "admiration", "poem": "白椿 黒髪の上に 散りかかる"},
        {"ja": "水仙", "en": "Daffodil", "kotoba": "self-love", "poem": "水仙や 白き日の如く 瓶のなか"},
        {"ja": "梅", "en": "Winter Plum", "kotoba": "perseverance", "poem": "梅一輪 一輪ほどの 暖かさ"},
        {"ja": "山茶花", "en": "Camellia", "kotoba": "modesty", "poem": "山茶花の 落ちてโหลの 古りにけり"},
    ],
}

# Elegant mood messages
MOODS = [
    {"ja": "今日は自分を大切にする日", "en": "A day to cherish yourself"},
    {"ja": "深呼吸して、リラックス", "en": "Take a deep breath and relax"},
    {"ja": "小さな幸せを見つけて", "en": "Find small moments of joy"},
    {"ja": "季節の移ろいを感じて", "en": "Feel the changing of seasons"},
    {"ja": "お茶を一杯、ゆっくりと", "en": "A cup of tea, slowly"},
    {"ja": "今日も一日お疲れ様", "en": "Well done for today"},
]


class MoodCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

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

        # Pick flower and mood based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        seasonal_flowers = FLOWERS.get(season, FLOWERS["spring"])
        flower = random.choice(seasonal_flowers)
        mood = random.choice(MOODS)
        random.seed()

        # Get flower image from Wikipedia
        flower_image = get_seasonal_flower_image(flower["ja"], (224, 304))
        
        # Save image to temporary file for HTML rendering
        flower_image_url = None
        if flower_image:
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp') as f:
                flower_image.save(f, 'PNG')
                flower_image_url = f'file://{f.name}'

        # Try HTML render first, fall back to PIL
        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "flower": flower,
                "mood": mood,
                "flower_image": flower_image_url,
            }
            
            image = self.render_image(dimensions_for_render, "mood_card.html", "mood_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL rendering
        return self._draw_card_pil(dimensions, orientation, flower, mood, season_info, palette, settings, now, flower_image)

    def _draw_card_pil(self, dimensions, orientation, flower, mood, season_info, palette, settings, now, flower_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Create base image
        bg_color = '#FAF8F5'
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Fonts
        font_flower = get_font("Noto Serif JP", int(w * 0.08))
        font_name = get_font("Noto Sans JP", int(w * 0.04))
        font_kotoba = get_font("Noto Serif JP", int(w * 0.035))
        font_mood = get_font("Noto Sans JP", int(w * 0.03))

        # Photo frame area
        if flower_image:
            photo_x, photo_y = int(w * 0.06), int(h * 0.15)
            photo_w, photo_h = int(w * 0.28), int(h * 0.65)
            
            # Resize and paste
            photo_resized = flower_image.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (photo_x, photo_y))
            
            # Add border
            draw = ImageDraw.Draw(img)
            draw.rectangle([photo_x-2, photo_y-2, photo_x+photo_w+2, photo_y+photo_h+2], 
                          outline='#E0D8C8', width=2)
            
            text_x = photo_x + photo_w + int(w * 0.06)
        else:
            text_x = int(w * 0.1)

        # Flower kanji
        draw.text((text_x, int(h * 0.2)), flower["ja"], font=font_flower, fill='#2C2C2C')
        
        # English name
        draw.text((text_x, int(h * 0.35)), flower["en"], font=font_name, fill='#666666')
        
        # 花言葉
        draw.text((text_x, int(h * 0.45)), f"花言葉: {flower['kotoba']}", font=font_kotoba, fill='#8B7355')
        
        # Mood message
        draw.text((text_x, int(h * 0.6)), mood["ja"], font=font_mood, fill='#666666')
        draw.text((text_x, int(h * 0.67)), mood["en"], font=font_mood, fill='#999999')
        
        # Poem
        if flower.get("poem"):
            draw.text((text_x, int(h * 0.8)), flower["poem"], font=get_font("Noto Serif JP", int(w * 0.025)), fill='#999999')

        return img
