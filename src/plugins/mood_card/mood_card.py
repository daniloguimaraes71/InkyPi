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

# Seasonal flowers with 花言葉 (flower language) - more sophisticated
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

# Elegant mood messages - more poetic
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

        return self._draw_card(dimensions, orientation, flower, mood, season_info, palette, settings, now)

    def _draw_card(self, dimensions, orientation, flower, mood, season_info, palette, settings, now):
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

        # Center - Flower kanji as main visual
        center_x = int(w * 0.35)
        center_y = int(h * 0.40)
        
        # Large flower kanji - elegant and prominent
        draw.text((center_x, center_y), flower["ja"], font=design.fonts['display'], 
                 fill=design.COLORS['text_primary'], anchor="mm")
        
        # English name below
        draw.text((center_x, center_y + int(h * 0.10)), flower["en"], 
                 font=design.fonts['h2'], fill=design.COLORS['text_secondary'], anchor="mm")
        
        # 花言葉 (flower language)
        kotoba_text = f"花言葉: {flower['kotoba']}"
        draw.text((center_x, center_y + int(h * 0.16)), kotoba_text, 
                 font=design.fonts['body'], fill=design.COLORS['accent_gold'], anchor="mm")

        # Vertical divider
        div_x = int(w * 0.55)
        draw.line([(div_x, int(h * 0.25)), (div_x, int(h * 0.75))], 
                 fill=design.COLORS['divider'], width=1)

        # Right side - Mood message
        right_x = int(w * 0.62)
        mood_y = int(h * 0.30)
        
        # Section header
        mood_y = design.draw_section(draw, "Mood", mood_y)
        
        # Mood message
        draw.text((right_x, mood_y), mood["ja"], font=design.fonts['h2'], 
                 fill=design.COLORS['text_primary'])
        mood_y += int(h * 0.06)
        
        # English translation
        draw.text((right_x, mood_y), mood["en"], font=design.fonts['body'], 
                 fill=design.COLORS['text_secondary'])
        mood_y += int(h * 0.08)

        # Poem - haiku or tanka
        if flower.get("poem"):
            draw.text((right_x, mood_y), flower["poem"], font=design.fonts['caption'], 
                     fill=design.COLORS['text_light'])

        # Footer
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info)

        return img
