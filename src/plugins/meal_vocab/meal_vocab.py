import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Curated Portuguese vocabulary by theme
VOCABULARY = [
    {"pt": "Bom dia", "ja": "おはようございます", "en": "Good morning", "theme": "greeting"},
    {"pt": "Obrigada", "ja": "ありがとう", "en": "Thank you", "theme": "greeting"},
    {"pt": "Por favor", "ja": "お願いします", "en": "Please", "theme": "greeting"},
    {"pt": "Água", "ja": "水", "en": "Water", "theme": "food"},
    {"pt": "Café", "ja": "コーヒー", "en": "Coffee", "theme": "food"},
    {"pt": "Pão", "ja": "パン", "en": "Bread", "theme": "food"},
    {"pt": "Arroz", "ja": "ご飯", "en": "Rice", "theme": "food"},
    {"pt": "Fruta", "ja": "フルーツ", "en": "Fruit", "theme": "food"},
    {"pt": "Queijo", "ja": "チーズ", "en": "Cheese", "theme": "food"},
    {"pt": "Vinho", "ja": "ワイン", "en": "Wine", "theme": "food"},
    {"pt": "Sol", "ja": "太陽", "en": "Sun", "theme": "nature"},
    {"pt": "Lua", "ja": "月", "en": "Moon", "theme": "nature"},
    {"pt": "Flor", "ja": "花", "en": "Flower", "theme": "nature"},
    {"pt": "Mar", "ja": "海", "en": "Sea", "theme": "nature"},
    {"pt": "Céu", "ja": "空", "en": "Sky", "theme": "nature"},
    {"pt": "Chuva", "ja": "雨", "en": "Rain", "theme": "nature"},
    {"pt": "Vento", "ja": "風", "en": "Wind", "theme": "nature"},
    {"pt": "Estrela", "ja": "星", "en": "Star", "theme": "nature"},
    {"pt": "Livro", "ja": "本", "en": "Book", "theme": "daily"},
    {"pt": "Música", "ja": "音楽", "en": "Music", "theme": "daily"},
    {"pt": "Caminhar", "ja": "歩く", "en": "To walk", "theme": "daily"},
    {"pt": "Amigo", "ja": "友達", "en": "Friend", "theme": "people"},
    {"pt": "Família", "ja": "家族", "en": "Family", "theme": "people"},
    {"pt": "Saudade", "ja": "懐かしさ", "en": "Longing/nostalgia", "theme": "emotion"},
    {"pt": "Feliz", "ja": "幸せ", "en": "Happy", "theme": "emotion"},
    {"pt": "Bonito", "ja": "美しい", "en": "Beautiful", "theme": "adjective"},
    {"pt": "Pequeno", "ja": "小さい", "en": "Small", "theme": "adjective"},
    {"pt": "Grande", "ja": "大きい", "en": "Big", "theme": "adjective"},
    {"pt": "Quente", "ja": "温かい", "en": "Warm/hot", "theme": "adjective"},
    {"pt": "Frio", "ja": "寒い", "en": "Cold", "theme": "adjective"},
]

# Simple meal suggestions
MEALS = [
    {"ja": "おにぎりと味噌汁", "en": "Rice balls and miso soup", "emoji": "🍙"},
    {"ja": "パンとコーヒー", "en": "Bread and coffee", "emoji": "☕"},
    {"ja": "パスタとサラダ", "en": "Pasta and salad", "emoji": "🍝"},
    {"ja": "カレーとナン", "en": "Curry and naan", "emoji": "🍛"},
    {"ja": "お寿司", "en": "Sushi", "emoji": "🍣"},
    {"ja": "ラーメン", "en": "Ramen", "emoji": "🍜"},
    {"ja": "たこ焼き", "en": "Takoyaki", "emoji": "🐙"},
    {"ja": "お好み焼き", "en": "Okonomiyaki", "emoji": "🥞"},
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

        # Pick vocabulary and meal
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        vocab = random.choice(VOCABULARY)
        meal = random.choice(MEALS)
        random.seed()  # Reset random state

        return self._draw_card(dimensions, vocab, meal, season_info, palette, settings, now)

    def _draw_card(self, dimensions, vocab, meal, season_info, palette, settings, now):
        w, h = dimensions
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", palette.get("bg", "#F8F5F0")), "RGB")

        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", palette.get("primary", "#333333")), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#888888"), "RGB")

        font_title = get_font("Noto Serif JP", int(w * 0.06))
        font_word = get_font("Noto Serif JP", int(w * 0.1))
        font_body = get_font("Noto Sans JP", int(w * 0.04))
        font_small = get_font("Noto Sans JP", int(w * 0.03))
        font_emoji = get_font("Noto Sans JP", int(w * 0.08))

        # Header
        draw.text((w * 0.08, h * 0.06), "今日の Portuguese", font=font_title, fill=primary + (200,))

        # Vocabulary section
        draw.text((w * 0.08, h * 0.18), vocab["pt"], font=font_word, fill=primary)
        draw.text((w * 0.08, h * 0.32), vocab["ja"], font=font_title, fill=primary)
        draw.text((w * 0.08, h * 0.40), vocab["en"], font=font_body, fill=primary + (150,))

        # Divider
        draw.line([(w * 0.08, h * 0.50), (w * 0.92, h * 0.50)], fill=accent + (80,), width=1)

        # Meal section
        draw.text((w * 0.08, h * 0.54), "今日のランチ", font=font_title, fill=primary + (200,))
        draw.text((w * 0.08, h * 0.64), meal["ja"], font=font_title, fill=primary)
        draw.text((w * 0.08, h * 0.72), meal["en"], font=font_body, fill=primary + (150,))

        # Date and season footer
        draw.line([(w * 0.08, h * 0.84), (w * 0.92, h * 0.84)], fill=accent + (80,), width=1)

        date_str = now.strftime("%A, %B %d")
        draw.text((w * 0.08, h * 0.87), date_str, font=font_small, fill=primary + (150,))

        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            draw.text((w * 0.92, h * 0.87), season_label, font=font_small, fill=accent + (180,), anchor="rt")

        return img
