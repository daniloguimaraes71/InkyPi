import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
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
    {"ja": "今日は自分を大切にする日", "en": "A day to cherish yourself", "poem": ""},
    {"ja": "深呼吸して、リラックス", "en": "Take a deep breath and relax", "poem": ""},
    {"ja": "小さな幸せを見つけて", "en": "Find small moments of joy", "poem": ""},
    {"ja": "季節の移ろいを感じて", "en": "Feel the changing of seasons", "poem": ""},
    {"ja": "お茶を一杯、ゆっくりと", "en": "A cup of tea, slowly", "poem": ""},
    {"ja": "今日も一日お疲れ様", "en": "Well done for today", "poem": ""},
]


class MoodCard(BasePlugin):
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

        # Pick flower and mood based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        seasonal_flowers = FLOWERS.get(season, FLOWERS["spring"])
        flower = random.choice(seasonal_flowers)
        mood = random.choice(MOODS)
        random.seed()

        return self._draw_card(dimensions, flower, mood, season_info, palette, settings, now)

    def _draw_card(self, dimensions, flower, mood, season_info, palette, settings, now):
        w, h = dimensions
        
        # Elegant background with subtle gradient
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", "#FAFAF8"), "RGB")
        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", "#2C2C2C"), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#8B7355"), "RGB")
        secondary = ImageColor.getcolor(palette.get("secondary", "#C4B99C"), "RGB")

        # Fonts - elegant hierarchy
        font_flower_kanji = get_font("Noto Serif JP", int(w * 0.14))
        font_flower_name = get_font("Noto Serif JP", int(w * 0.05))
        font_kotoba = get_font("Noto Sans JP", int(w * 0.035))
        font_poem = get_font("Noto Serif JP", int(w * 0.032))
        font_mood = get_font("Noto Serif JP", int(w * 0.045))
        font_small = get_font("Noto Sans JP", int(w * 0.028))

        # Center - Flower kanji as main visual
        center_x = int(w * 0.35)
        center_y = int(h * 0.35)
        
        # Large flower kanji - elegant and prominent
        draw.text((center_x, center_y), flower["ja"], font=font_flower_kanji, fill=primary, anchor="mm")
        
        # English name below
        draw.text((center_x, center_y + int(h * 0.12)), flower["en"], font=font_flower_name, fill=primary + (180,), anchor="mm")
        
        # 花言葉 (flower language)
        kotoba_text = f"花言葉: {flower['kotoba']}"
        draw.text((center_x, center_y + int(h * 0.20)), kotoba_text, font=font_kotoba, fill=accent, anchor="mm")

        # Vertical divider - elegant line
        div_x = int(w * 0.58)
        draw.line([(div_x, int(h * 0.20)), (div_x, int(h * 0.70))], fill=secondary + (80,), width=1)

        # Right side - Mood message
        right_x = int(w * 0.65)
        
        # Mood message
        draw.text((right_x, int(h * 0.30)), mood["ja"], font=font_mood, fill=primary)
        draw.text((right_x, int(h * 0.38)), mood["en"], font=font_kotoba, fill=primary + (180,))

        # Poem - haiku or tanka
        if flower.get("poem"):
            draw.text((right_x, int(h * 0.50)), flower["poem"], font=font_poem, fill=primary + (150,))

        # Bottom - Season and date
        footer_y = int(h * 0.82)
        left_x = int(w * 0.08)
        draw.line([(left_x, footer_y), (w - left_x, footer_y)], fill=secondary + (60,), width=1)
        
        # Date
        date_str = now.strftime("%Y年%m月%d日")
        draw.text((left_x, footer_y + int(h * 0.04)), date_str, font=font_small, fill=primary + (150,))
        
        # Micro-season with context
        if season_info:
            season_label = f"時候: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            draw.text((w - left_x, footer_y + int(h * 0.04)), season_label, font=font_small, fill=accent, anchor="rt")
            draw.text((w - left_x, footer_y + int(h * 0.08)), season_meaning, font=font_small, fill=primary + (120,), anchor="rt")

        return img
