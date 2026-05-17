import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Intermediate Portuguese vocabulary with themes
VOCABULARY = [
    {"pt": "Saudade", "ja": "懐かしさ・切なさ", "en": "A deep emotional longing", "theme": "emotion", "example": "Tenho saudade da minha avó."},
    {"pt": "Desenrascanço", "ja": "場当たり的な対応", "en": "To improvise a solution", "theme": "daily", "example": "Vou me desenrascar com o que tenho."},
    {"pt": "Cafuné", "ja": "頭を撫でること", "en": "The act of stroking someone's hair", "theme": "affection", "example": "Ela fez cafuné no filho."},
    {"pt": "Fofura", "ja": "かわいさ・愛らしさ", "en": "Something adorable or cute", "theme": "adjective", "example": "Que fofura de bebê!"},
    {"pt": "Xodó", "ja": "大切な人・お気に入り", "en": "A cherished person or thing", "theme": "affection", "example": "Esse livro é meu xodó."},
    {"pt": "Ansiedade", "ja": "不安・焦り", "en": "Anxiety, restlessness", "theme": "emotion", "example": "Sinto muita ansiedade antes de viajar."},
    {"pt": "Aproveitar", "ja": "楽しむ・活用する", "en": "To enjoy, to make the most of", "theme": "daily", "example": "Vou aproveitar o dia de folga."},
    {"pt": "Simpático", "ja": "感じがいい・親しみやすい", "en": "Friendly, likeable", "theme": "adjective", "example": "O atendente foi muito simpático."},
    {"pt": "Ficar com", "ja": "気になる・気にする", "en": "To be concerned about", "theme": "expression", "example": "Fiquei com medo de perder o voo."},
    {"pt": "Dar um jeito", "ja": "何とかする", "en": "To find a way, to manage", "theme": "expression", "example": "Vou dar um jeito de chegar a tempo."},
    {"pt": "Tô de olho", "ja": "注目している", "en": "I'm keeping an eye on it", "theme": "expression", "example": "Tô de olho nessa promoção."},
    {"pt": "Bora lá", "ja": "さあ行こう", "en": "Let's go!", "theme": "expression", "example": "Bora lá jantar!"},
    {"pt": "Que saudade!", "ja": "会いたかった！", "en": "I missed you so much!", "theme": "expression", "example": "Que saudade de você!"},
    {"pt": "Legal", "ja": "いいね・素敵", "en": "Cool, nice", "theme": "adjective", "example": "Essa música é muito legal."},
    {"pt": "Beleza", "ja": "了解・わかった", "en": "Got it, okay", "theme": "expression", "example": "Beleza, nos vemos amanhã."},
    {"pt": "Pôr do sol", "ja": "夕日・日の入り", "en": "Sunset", "theme": "nature", "example": "O pôr do sol na praia é lindo."},
    {"pt": "Cheirinho de", "ja": "～の香り", "en": "A hint of scent", "theme": "nature", "example": "Cheirinho de café fresquinho."},
    {"pt": "Madrugada", "ja": "早朝・夜明け前", "en": "Early morning hours", "theme": "time", "example": "Estudei até a madrugada."},
    {"pt": "Vontade de", "ja": "～したい気分", "en": "A desire to, feeling like", "theme": "emotion", "example": "Tenho vontade de viajar agora."},
    {"pt": "Faz sentido", "ja": "意味がある・納得できる", "en": "It makes sense", "theme": "expression", "example": "O que você disse faz sentido."},
]

MEALS = [
    {"ja": "おにぎりと温かい味噌汁", "en": "Rice balls with warm miso soup", "emoji": "🍙"},
    {"ja": "フレンチトーストと珈琲", "en": "French toast with coffee", "emoji": "☕"},
    {"ja": "パスタとフレッシュサラダ", "en": "Pasta with fresh salad", "emoji": "🍝"},
    {"ja": "カレーとガーリックナン", "en": "Curry with garlic naan", "emoji": "🍛"},
    {"ja": "お寿司とお味噌汁", "en": "Sushi with miso soup", "emoji": "🍣"},
    {"ja": "自家製ラーメン", "en": "Homemade ramen", "emoji": "🍜"},
    {"ja": "たこ焼きとおでん", "en": "Takoyaki and oden", "emoji": "🐙"},
    {"ja": "お好み焼きと冷やし@update", "en": "Okonomiyaki with cold noodles", "emoji": "🥞"},
]


class MealVocab(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        # Pick vocabulary and meal based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        vocab = random.choice(VOCABULARY)
        meal = random.choice(MEALS)
        random.seed()

        return self._draw_card(dimensions, vocab, meal, season_info, palette, settings, now)

    def _draw_card(self, dimensions, vocab, meal, season_info, palette, settings, now):
        w, h = dimensions
        
        # Elegant background with subtle gradient
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", "#FAFAF8"), "RGB")
        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", "#2C2C2C"), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#8B7355"), "RGB")
        secondary = ImageColor.getcolor(palette.get("secondary", "#C4B99C"), "RGB")

        # Fonts - elegant hierarchy
        font_title = get_font("Noto Serif JP", int(w * 0.055))
        font_word = get_font("Noto Serif JP", int(w * 0.11))
        font_meaning = get_font("Noto Sans JP", int(w * 0.038))
        font_example = get_font("Noto Sans JP", int(w * 0.03))
        font_section = get_font("Noto Serif JP", int(w * 0.042))
        font_small = get_font("Noto Sans JP", int(w * 0.028))

        # Left side - Vocabulary
        left_x = int(w * 0.08)
        
        # Subtle section indicator
        draw.line([(left_x, int(h * 0.12)), (left_x + int(w * 0.03), int(h * 0.12))], fill=accent, width=2)
        draw.text((left_x + int(w * 0.04), int(h * 0.10)), "Vocabulário", font=font_small, fill=accent)
        
        # Portuguese word - elegant and prominent
        draw.text((left_x, int(h * 0.18)), vocab["pt"], font=font_word, fill=primary)
        
        # Japanese meaning
        draw.text((left_x, int(h * 0.34)), vocab["ja"], font=font_title, fill=primary)
        
        # English meaning - subtle
        draw.text((left_x, int(h * 0.44)), vocab["en"], font=font_meaning, fill=primary + (180,))
        
        # Example sentence - italic style
        draw.text((left_x, int(h * 0.56)), f'"{vocab["example"]}"', font=font_example, fill=primary + (140,))

        # Vertical divider - elegant line
        div_x = int(w * 0.52)
        draw.line([(div_x, int(h * 0.15)), (div_x, int(h * 0.75))], fill=secondary + (100,), width=1)

        # Right side - Meal
        right_x = int(w * 0.58)
        
        # Section indicator
        draw.line([(right_x, int(h * 0.12)), (right_x + int(w * 0.03), int(h * 0.12))], fill=accent, width=2)
        draw.text((right_x + int(w * 0.04), int(h * 0.10)), "Almoço", font=font_small, fill=accent)
        
        # Meal suggestion
        draw.text((right_x, int(h * 0.18)), meal["ja"], font=font_section, fill=primary)
        draw.text((right_x, int(h * 0.28)), meal["en"], font=font_meaning, fill=primary + (180,))

        # Bottom - Season and date
        bottom_y = int(h * 0.82)
        draw.line([(left_x, bottom_y), (w - left_x, bottom_y)], fill=secondary + (60,), width=1)
        
        # Date - clean format
        date_str = now.strftime("%Y年%m月%d日")
        draw.text((left_x, bottom_y + int(h * 0.04)), date_str, font=font_small, fill=primary + (150,))
        
        # Micro-season - with context
        if season_info:
            season_label = f"時候の挨拶: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            draw.text((w - left_x, bottom_y + int(h * 0.04)), season_label, font=font_small, fill=accent, anchor="rt")
            draw.text((w - left_x, bottom_y + int(h * 0.08)), season_meaning, font=font_small, fill=primary + (120,), anchor="rt")

        return img
