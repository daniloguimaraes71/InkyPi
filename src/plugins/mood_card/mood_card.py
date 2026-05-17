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
        
        flower_image_data_uri = self.image_to_data_uri(flower_image)

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
                "flower_image": flower_image_data_uri,
            }
            
            image = self.render_image(dimensions_for_render, "mood_card.html", "mood_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL rendering
        return self._draw_card_pil(dimensions, orientation, flower, mood, season_info, palette, settings, now, flower_image)

    def _draw_card_pil(self, dimensions, orientation, flower, mood, season_info, palette, settings, now, flower_image):
        """Elegant flower + mood card with photo frame."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        img = Image.new('RGB', (w, h), '#FAF8F5')
        draw = ImageDraw.Draw(img)

        px = int(w * 0.05)
        py = int(h * 0.07)
        photo_w = int(w * 0.28)
        photo_h = h - py * 2
        gap = int(w * 0.05)
        text_x = px + photo_w + gap

        f_flower = get_font("Noto Serif JP", int(w * 0.07))
        f_en = get_font("Noto Serif JP", int(w * 0.028))
        f_kotoba = get_font("Noto Sans JP", int(w * 0.02))
        f_mood = get_font("Noto Serif JP", int(w * 0.024))
        f_mood_en = get_font("Noto Sans JP", int(w * 0.018))
        f_poem = get_font("Noto Serif JP", int(w * 0.016))
        f_ms = get_font("Noto Serif JP", int(w * 0.016))
        f_ms_en = get_font("Noto Sans JP", int(w * 0.012))

        # Photo frame (left)
        if flower_image:
            img.paste(flower_image.resize((photo_w, photo_h), Image.Resampling.LANCZOS), (px, py))
            draw = ImageDraw.Draw(img)
            draw.rectangle([px-2, py-2, px+photo_w+2, py+photo_h+2], outline='#E0D8C8', width=1)
        else:
            draw.rectangle([px, py, px+photo_w, py+photo_h], fill='#E8E4D9', outline='#E0D8C8', width=1)
            bbox = draw.textbbox((0, 0), flower["ja"], font=f_flower)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((px + (photo_w - tw) // 2, py + (photo_h - th) // 2), flower["ja"], font=f_flower, fill='#888888')

        # Flower name
        draw.text((text_x, py), flower["ja"], font=f_flower, fill='#2C2C2C')
        draw.text((text_x, py + int(h * 0.1)), flower["en"], font=f_en, fill='#555555')

        # 花言葉 with accent bar
        ky_y = py + int(h * 0.18)
        draw.line([(text_x, ky_y), (text_x + 3, ky_y + int(h * 0.06))], fill='#B87333', width=2)
        draw.text((text_x + int(w * 0.02), ky_y), f"花言葉: {flower['kotoba']}", font=f_kotoba, fill='#8B7355')

        # Divider
        div_y = ky_y + int(h * 0.08)
        draw.line([(text_x, div_y), (text_x + int(w * 0.35), div_y)], fill='#E0D8C8', width=1)

        # Mood message
        my = div_y + int(h * 0.05)
        draw.text((text_x, my), mood["ja"], font=f_mood, fill='#2C2C2C')
        draw.text((text_x, my + int(h * 0.04)), mood["en"], font=f_mood_en, fill='#555555')

        # Poem
        if flower.get("poem"):
            draw.text((text_x, my + int(h * 0.1)), flower["poem"], font=f_poem, fill='#888888')

        # Micro-season
        if season_info:
            ms_x = w - px
            ms_y = h - int(h * 0.055)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill='#8B7355')
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.022)), e, font=f_ms_en, fill='#888888')

        return img
