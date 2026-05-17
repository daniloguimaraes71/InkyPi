import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.card_design import CardDesign, wrap_text
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
    {"ja": "おにぎりと温かい味噌汁", "en": "Rice balls with warm miso soup"},
    {"ja": "フレンチトーストと珈琲", "en": "French toast with coffee"},
    {"ja": "パスタとフレッシュサラダ", "en": "Pasta with fresh salad"},
    {"ja": "カレーとガーリックナン", "en": "Curry with garlic naan"},
    {"ja": "お寿司とお味噌汁", "en": "Sushi with miso soup"},
    {"ja": "自家製ラーメン", "en": "Homemade ramen"},
    {"ja": "たこ焼きとおでん", "en": "Takoyaki and oden"},
    {"ja": "お好み焼きと冷やし@update", "en": "Okonomiyaki with cold noodles"},
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

        return self._draw_card(dimensions, orientation, vocab, meal, season_info, palette, settings, now)

    def _draw_card(self, dimensions, orientation, vocab, meal, season_info, palette, settings, now):
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Initialize design system
        design = CardDesign((w, h), orientation)
        
        # Create base card
        img = design.create_base_card(palette=palette)
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = design.draw_header(draw, "今日の Português", 
                                  "Vocabulário & Almoço")

        # Left side - Vocabulary
        left_x = design.margin
        
        # Section header
        y_pos = design.draw_section(draw, "Vocabulário", y_pos)
        
        # Portuguese word - large and prominent
        draw.text((left_x, y_pos), vocab["pt"], font=design.fonts['display'], 
                 fill=design.COLORS['text_primary'])
        y_pos += int(h * 0.12)
        
        # Japanese meaning
        draw.text((left_x, y_pos), vocab["ja"], font=design.fonts['h2'], 
                 fill=design.COLORS['text_primary'])
        y_pos += int(h * 0.06)
        
        # English meaning
        draw.text((left_x, y_pos), vocab["en"], font=design.fonts['body'], 
                 fill=design.COLORS['text_secondary'])
        y_pos += int(h * 0.05)
        
        # Example sentence
        example_y = y_pos + int(h * 0.02)
        draw.text((left_x, example_y), f'"{vocab["example"]}"', font=design.fonts['caption'], 
                 fill=design.COLORS['text_light'])

        # Vertical divider
        div_x = int(w * 0.52)
        draw.line([(div_x, int(h * 0.25)), (div_x, int(h * 0.75))], 
                 fill=design.COLORS['divider'], width=1)

        # Right side - Meal
        right_x = int(w * 0.58)
        meal_y = y_pos - int(h * 0.15)
        
        # Section header
        meal_y = design.draw_section(draw, "Almoço", meal_y)
        
        # Meal suggestion
        draw.text((right_x, meal_y), meal["ja"], font=design.fonts['h2'], 
                 fill=design.COLORS['text_primary'])
        meal_y += int(h * 0.06)
        
        # English translation
        draw.text((right_x, meal_y), meal["en"], font=design.fonts['body'], 
                 fill=design.COLORS['text_secondary'])

        # Footer
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info)

        return img
