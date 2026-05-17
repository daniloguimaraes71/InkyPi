import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_food_image
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Intermediate Portuguese vocabulary
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
    {"ja": "おにぎりと温かい味噌汁", "en": "Rice balls with warm miso soup", "food": "おにぎり"},
    {"ja": "フレンチトーストと珈琲", "en": "French toast with coffee", "food": "珈琲"},
    {"ja": "パスタとフレッシュサラダ", "en": "Pasta with fresh salad", "food": "パスタ"},
    {"ja": "カレーとガーリックナン", "en": "Curry with garlic naan", "food": "カレー"},
    {"ja": "お寿司とお味噌汁", "en": "Sushi with miso soup", "food": "寿司"},
    {"ja": "自家製ラーメン", "en": "Homemade ramen", "food": "ラーメン"},
    {"ja": "たこ焼きとおでん", "en": "Takoyaki and oden", "food": "たこ焼き"},
    {"ja": "お好み焼き", "en": "Okonomiyaki", "food": "お好み焼き"},
]


class MealVocab(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        # Pick vocabulary and meal based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        vocab = random.choice(VOCABULARY)
        meal = random.choice(MEALS)
        random.seed()

        # Get food image from Wikipedia
        food_image = get_food_image(meal.get("food", "寿司"), (300, 200))
        
        # Save image to temporary file for HTML rendering
        food_image_url = None
        if food_image:
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp') as f:
                food_image.save(f, 'PNG')
                food_image_url = f'file://{f.name}'

        # Try HTML render first, fall back to PIL
        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "vocab": vocab,
                "meal": meal,
                "food_image": food_image_url,
            }
            
            image = self.render_image(dimensions_for_render, "meal_vocab.html", "meal_vocab.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL rendering
        return self._draw_card_pil(dimensions, orientation, vocab, meal, season_info, palette, settings, now, food_image)

    def _draw_card_pil(self, dimensions, orientation, vocab, meal, season_info, palette, settings, now, food_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Create base image
        bg_color = '#FAF8F5'
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Fonts
        font_word = get_font("Noto Sans JP", int(w * 0.08))
        font_ja = get_font("Noto Serif JP", int(w * 0.045))
        font_en = get_font("Noto Sans JP", int(w * 0.03))
        font_section = get_font("Noto Sans JP", int(w * 0.025))

        # Left side - Vocabulary
        draw.text((int(w * 0.08), int(h * 0.15)), "Palavra do Dia", font=font_section, fill='#8B7355')
        draw.text((int(w * 0.08), int(h * 0.22)), vocab["pt"], font=font_word, fill='#2C2C2C')
        draw.text((int(w * 0.08), int(h * 0.38)), vocab["ja"], font=font_ja, fill='#666666')
        draw.text((int(w * 0.08), int(h * 0.48)), vocab["en"], font=font_en, fill='#999999')
        draw.text((int(w * 0.08), int(h * 0.58)), f'"{vocab["example"]}"', font=font_en, fill='#999999')

        # Divider
        draw.line([(int(w * 0.5), int(h * 0.15)), (int(w * 0.5), int(h * 0.85))], fill='#E0D8C8', width=1)

        # Right side - Meal
        draw.text((int(w * 0.55), int(h * 0.15)), "今日のランチ", font=font_section, fill='#7A8B6F')
        draw.text((int(w * 0.55), int(h * 0.22)), meal["ja"], font=font_ja, fill='#2C2C2C')
        draw.text((int(w * 0.55), int(h * 0.35)), meal["en"], font=font_en, fill='#666666')
        
        # Food image
        if food_image:
            img_x, img_y = int(w * 0.55), int(h * 0.5)
            img_w, img_h = int(w * 0.35), int(h * 0.35)
            food_resized = food_image.resize((img_w, img_h), Image.Resampling.LANCZOS)
            img.paste(food_resized, (img_x, img_y))

        return img
