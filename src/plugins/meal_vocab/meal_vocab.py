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
        
        # Save image to static directory for HTML rendering
        food_image_url = None
        if food_image:
            import os
            static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'images', 'cache')
            os.makedirs(static_dir, exist_ok=True)
            image_path = os.path.join(static_dir, 'meal_food.png')
            food_image.save(image_path, 'PNG')
            food_image_url = f'/static/images/cache/meal_food.png'

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
        """Elegant 50/50 split with vocab and meal."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        img = Image.new('RGB', (w, h), '#FAF8F5')
        draw = ImageDraw.Draw(img)

        px = int(w * 0.06)
        py = int(h * 0.08)
        mid_x = w // 2

        f_label = get_font("Noto Sans JP", int(w * 0.016))
        f_vocab = get_font("Noto Sans JP", int(w * 0.065))
        f_pron = get_font("Noto Sans JP", int(w * 0.02))
        f_meaning = get_font("Noto Serif JP", int(w * 0.024))
        f_example = get_font("Noto Sans JP", int(w * 0.018))
        f_meal = get_font("Noto Serif JP", int(w * 0.032))
        f_meal_desc = get_font("Noto Sans JP", int(w * 0.02))
        f_ms = get_font("Noto Serif JP", int(w * 0.016))
        f_ms_en = get_font("Noto Sans JP", int(w * 0.012))

        # Left - Vocabulary
        draw.text((px, py), "Palavra do Dia", font=f_label, fill='#8B7355')
        draw.text((px, py + int(h * 0.05)), vocab["pt"], font=f_vocab, fill='#B87333')
        draw.text((px, py + int(h * 0.14)), vocab["ja"], font=f_meaning, fill='#555555')
        draw.text((px, py + int(h * 0.2)), f'"{vocab["example"]}"', font=f_example, fill='#888888')

        # Vertical divider
        draw.line([(mid_x, int(h * 0.1)), (mid_x, int(h * 0.85))], fill='#E0D8C8', width=1)

        # Right - Meal
        rx = mid_x + int(w * 0.05)
        draw.text((rx, py), "昼食のヒント", font=f_label, fill='#8B7355')
        draw.text((rx, py + int(h * 0.05)), meal["ja"], font=f_meal, fill='#2C2C2C')
        draw.text((rx, py + int(h * 0.12)), meal["en"], font=f_meal_desc, fill='#555555')

        # Food image with frame
        if food_image:
            ix = rx
            iy = py + int(h * 0.22)
            iw = int(w * 0.18)
            ih = int(w * 0.18)
            img.paste(food_image.resize((iw, ih), Image.Resampling.LANCZOS), (ix, iy))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ix-2, iy-2, ix+iw+2, iy+ih+2], outline='#E0D8C8', width=1)

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
