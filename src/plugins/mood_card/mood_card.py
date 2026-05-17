import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.card_design import CardDesign, ImageLoader
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

# Flower photos for visual appeal
FLOWER_PHOTOS = {
    "spring": [
        "https://images.unsplash.com/photo-1522383225653-ed111181a951?w=400",
        "https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=400",
    ],
    "summer": [
        "https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=400",
        "https://images.unsplash.com/photo-1490750967868-88aa4f44baee?w=400",
    ],
    "autumn": [
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400",
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400",
    ],
    "winter": [
        "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=400",
        "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=400",
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
        photo_url = random.choice(FLOWER_PHOTOS.get(season, FLOWER_PHOTOS["spring"]))
        random.seed()

        # Load flower photo
        photo = self._load_flower_photo(photo_url, dimensions)

        return self._draw_card(dimensions, orientation, flower, mood, season_info, palette, settings, now, photo)

    def _load_flower_photo(self, photo_url, dimensions):
        """Load a flower photo for visual appeal."""
        try:
            target_size = (int(dimensions[0] * 0.3), int(dimensions[1] * 0.4))
            return ImageLoader.load_and_fit(photo_url, target_size)
        except Exception as e:
            logger.warning(f"Failed to load flower photo: {e}")
            return None

    def _draw_card(self, dimensions, orientation, flower, mood, season_info, palette, settings, now, photo):
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Initialize design system
        design = CardDesign((w, h), orientation)
        
        # Create base card
        img = design.create_base_card(palette=palette)
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = design.draw_header(draw, "今日の花", 
                                  "Flower & Mood")

        # Photo section (if available)
        if photo:
            photo_x = design.margin
            photo_y = y_pos
            photo_w = int(w * 0.25)
            photo_h = int(h * 0.4)
            
            # Paste photo
            photo_resized = photo.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (photo_x, photo_y))
            
            # Add border
            draw = ImageDraw.Draw(img)
            draw.rectangle([photo_x-1, photo_y-1, photo_x+photo_w+1, photo_y+photo_h+1], 
                          outline=design.COLORS['divider'], width=1)
            
            # Text on the right
            text_x = photo_x + photo_w + int(w * 0.04)
            text_w = w - text_x - design.margin
        else:
            text_x = design.margin
            text_w = w - 2 * design.margin

        # Flower kanji - large and prominent
        flower_y = y_pos + int(h * 0.05)
        draw.text((text_x, flower_y), flower["ja"], font=design.fonts['display'], 
                 fill=design.COLORS['text_primary'])
        flower_y += int(h * 0.12)
        
        # English name
        draw.text((text_x, flower_y), flower["en"], font=design.fonts['h2'], 
                 fill=design.COLORS['text_secondary'])
        flower_y += int(h * 0.06)
        
        # 花言葉 (flower language)
        kotoba_text = f"花言葉: {flower['kotoba']}"
        draw.text((text_x, flower_y), kotoba_text, font=design.fonts['body'], 
                 fill=design.COLORS['accent_gold'])
        flower_y += int(h * 0.08)

        # Poem
        if flower.get("poem"):
            draw.text((text_x, flower_y), flower["poem"], font=design.fonts['caption'], 
                     fill=design.COLORS['text_light'])

        # Mood section - below flower
        mood_y = int(h * 0.65)
        mood_y = design.draw_section(draw, "Mood", mood_y)
        
        # Mood message
        draw.text((design.margin, mood_y), mood["ja"], font=design.fonts['h3'], 
                 fill=design.COLORS['text_primary'])
        mood_y += int(h * 0.04)
        
        # English translation
        draw.text((design.margin, mood_y), mood["en"], font=design.fonts['body'], 
                 fill=design.COLORS['text_secondary'])

        # Footer - no micro-season
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info, show_season=False)

        return img
