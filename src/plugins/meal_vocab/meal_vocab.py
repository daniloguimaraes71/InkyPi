import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_food_image
from utils.app_utils import get_font
from utils.design_variants import get_variant
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

VOCABULARY = [
    {"pt": "Saudade", "ja": "懐かしさ・切なさ", "en": "A deep emotional longing for something absent", "theme": "emotion", "example": "Tenho saudade dos tempos de infância."},
    {"pt": "Desenrascanço", "ja": "場当たり的な対応力", "en": "The art of improvising solutions with limited resources", "theme": "daily", "example": "O desenrascanço brasileiro é lendário."},
    {"pt": "Cafuné", "ja": "頭を優しく撫でること", "en": "The act of gently stroking someone's hair as affection", "theme": "affection", "example": "Ela fez cafuné no filho até ele adormecer."},
    {"pt": "Melancolia", "ja": "憂鬱・物悲しさ", "en": "A gentle sadness, often with a poetic quality", "theme": "emotion", "example": "A melancolia do outono me inspira."},
    {"pt": "Euforia", "ja": "陶酔感・高揚", "en": "Intense excitement and happiness", "theme": "emotion", "example": "Sentiu euforia ao receber a notícia."},
    {"pt": "Nostalgia", "ja": "郷愁・懐古", "en": "Sentimental longing for the past", "theme": "emotion", "example": "A nostalgia toma conta de mim às vezes."},
    {"pt": "Empatia", "ja": "共感力", "en": "The ability to understand and share others' feelings", "theme": "emotion", "example": "Ela tem muita empatia pelos outros."},
    {"pt": "Resiliência", "ja": "回復力・適応力", "en": "The capacity to recover quickly from difficulties", "theme": "character", "example": "Sua resiliência é admirável."},
    {"pt": "Aproveitar", "ja": "楽しむ・活用する", "en": "To enjoy thoroughly or make the most of something", "theme": "daily", "example": "Vou aproveitar cada momento desta viagem."},
    {"pt": "Desabafar", "ja": "胸の内を明かす", "en": "To unburden oneself, to vent feelings", "theme": "emotion", "example": "Preciso desabafar com alguém."},
    {"pt": "Conciliar", "ja": "調和させる・両立する", "en": "To reconcile or harmonize different things", "theme": "daily", "example": "É difícil conciliar trabalho e família."},
    {"pt": "Perscrutar", "ja": "じっと見つめる・探る", "en": "To examine closely, to scrutinize", "theme": "intellectual", "example": "Ele perscrutou o horizonte em busca de respostas."},
    {"pt": "Murmurar", "ja": "つぶやく・ささやく", "en": "To speak softly or indistinctly", "theme": "daily", "example": "Ela murmurou algo que não entendi."},
    {"pt": "Vislumbrar", "ja": "かすかに見る・予感する", "en": "To glimpse or to have a vague idea of", "theme": "intellectual", "example": "Consigo vislumbrar um futuro melhor."},
    {"pt": "Subentender", "ja": "言外に含む・暗示する", "en": "To imply or to understand implicitly", "theme": "intellectual", "example": "Muito foi subentendido naquela conversa."},
    {"pt": "Transcender", "ja": "超越する", "en": "To go beyond ordinary limits", "theme": "philosophy", "example": "A arte pode transcender barreiras culturais."},
    {"pt": "Dar um jeito", "ja": "何とかする・解決策を見つける", "en": "To find a way, to manage somehow", "theme": "expression", "example": "Vou dar um jeito de resolver isso."},
    {"pt": "Ficar de olho", "ja": "注意深く見守る", "en": "To keep a close watch on something", "theme": "expression", "example": "Fique de olho nas suas coisas."},
    {"pt": "Pôr a mão na massa", "ja": "実際に手を動かす", "en": "To get down to work, to take action", "theme": "expression", "example": "Chega de planejar, vamos pôr a mão na massa."},
    {"pt": "Chover no molhado", "ja": "無駄を繰り返す", "en": "To repeat something unnecessarily", "theme": "expression", "example": "Dizer isso é chover no molhado."},
    {"pt": "Engolir sapos", "ja": "我慢する・耐え忍ぶ", "en": "To swallow insults, to endure silently", "theme": "expression", "example": "Às vezes precisamos engolir sapos."},
    {"pt": "Fazer das tripas coração", "ja": "全力を尽くす", "en": "To make a supreme effort", "theme": "expression", "example": "Ela fez das tripas coração para terminar."},
    {"pt": "Meter o pé", "ja": "逃げ出す・立ち去る", "en": "To leave quickly, to bolt", "theme": "expression", "example": "Quando viu a confusão, meteu o pé."},
    {"pt": "Virar a mesa", "ja": "形勢を逆転する", "en": "To turn the tables, to reverse a situation", "theme": "expression", "example": "O time virou a mesa no segundo tempo."},
    {"pt": "Madrugada", "ja": "夜明け前・深夜", "en": "The early morning hours before dawn", "theme": "time", "example": "Estudei até a madrugada para a prova."},
    {"pt": "Entardecer", "ja": "夕暮れ時", "en": "The time when day turns to evening", "theme": "nature", "example": "O entardecer na serra é mágico."},
    {"pt": "Amanhecer", "ja": "夜明け・朝の訪れ", "en": "The breaking of day, dawn", "theme": "nature", "example": "O amanhecer trouxe esperança."},
    {"pt": "Crepúsculo", "ja": "黄昏・薄明かり", "en": "The soft light after sunset", "theme": "nature", "example": "O crepúsculo pintou o céu de laranja."},
    {"pt": "Brisa", "ja": "そよ風", "en": "A gentle, refreshing breeze", "theme": "nature", "example": "A brisa do mar aliviou o calor."},
    {"pt": "Orvalho", "ja": "朝露", "en": "Dew drops on morning grass", "theme": "nature", "example": "O orvalho brilhava nas folhas."},
    {"pt": "Horizonte", "ja": "地平線・視野", "en": "The line where earth meets sky", "theme": "nature", "example": "Novos horizontes se abrem diante de nós."},
    {"pt": "Penumbra", "ja": "薄暗がり・半陰影", "en": "Partial shadow, dim light", "theme": "nature", "example": "A penumbra da tarde era acolhedora."},
    {"pt": "Simpático", "ja": "感じがいい・親しみやすい", "en": "Pleasant, likeable, friendly", "theme": "character", "example": "O atendente foi muito simpático."},
    {"pt": "Perspicaz", "ja": "鋭い・洞察力がある", "en": "Having keen insight, perceptive", "theme": "character", "example": "Ela é muito perspicaz nos negócios."},
    {"pt": "Tenaz", "ja": "粘り強い・不屈の", "en": "Persistent, determined, unyielding", "theme": "character", "example": "Sua tenaz dedicação impressiona."},
    {"pt": "Efêmero", "ja": "はかない・一時の", "en": "Lasting for a very short time", "theme": "philosophy", "example": "A beleza efêmera das flores."},
    {"pt": "Inefável", "ja": "言葉に表せない", "en": "Too great to be expressed in words", "theme": "philosophy", "example": "Uma alegria inefável tomou conta de mim."},
    {"pt": "Serendipidade", "ja": "偶然の幸運な発見", "en": "Finding something good by chance", "theme": "philosophy", "example": "Foi pura serendipidade encontrar aquele livro."},
    {"pt": "Dicotomia", "ja": "二律背反・二分法", "en": "A division into two contrasting parts", "theme": "intellectual", "example": "A dicotomia entre razão e emoção."},
    {"pt": "Pragmático", "ja": "実用的・現実的な", "en": "Dealing with things practically", "theme": "character", "example": "Ele é muito pragmático nas decisões."},
    {"pt": "Faz sentido", "ja": "意味がある・納得できる", "en": "It makes logical sense", "theme": "expression", "example": "O que você disse faz todo sentido."},
    {"pt": "Levar a sério", "ja": "真剣に受け止める", "en": "To take something seriously", "theme": "expression", "example": "Devemos levar a sério as mudanças climáticas."},
    {"pt": "Cair a ficha", "ja": "ようやく理解する", "en": "To finally understand, the penny drops", "theme": "expression", "example": "Demorou, mas caiu a ficha."},
    {"pt": "Bater o olho", "ja": "一目でわかる", "en": "To recognize at first glance", "theme": "expression", "example": "Bati o olho e soube que era ele."},
    {"pt": "Puxar a brasa", "ja": "自分に有利に話す", "en": "To pull the coals to one's sardine (favor oneself)", "theme": "expression", "example": "Ele sempre puxa a brasa para sua sardinha."},
    {"pt": "Encher linguiça", "ja": "話を引き延ばす", "en": "To pad out, to fill space unnecessarily", "theme": "expression", "example": "O discurso foi só encher linguiça."},
    {"pt": "Dar com os burros n'água", "ja": "失敗する・無駄になる", "en": "To come to nothing, to fail completely", "theme": "expression", "example": "Todos os planos deram com os burros n'água."},
    {"pt": "Fazer tempestade em copo d'água", "ja": "大げさに騒ぐ", "en": "To make a mountain out of a molehill", "theme": "expression", "example": "Não faça tempestade em copo d'água."},
]

MEALS = [
    {"ja": "おにぎりと温かい味噌汁", "en": "Rice balls with warm miso soup", "food": "おにぎり"},
    {"ja": "お寿司とお味噌汁", "en": "Sushi with miso soup", "food": "寿司"},
    {"ja": "自家製ラーメン", "en": "Homemade ramen", "food": "ラーメン"},
    {"ja": "たこ焼きとおでん", "en": "Takoyaki and oden", "food": "たこ焼き"},
    {"ja": "お好み焼き", "en": "Okonomiyaki", "food": "お好み焼き"},
    {"ja": "天ぷらそば", "en": "Tempura soba noodles", "food": "天ぷら"},
    {"ja": "うな丼と漬物", "en": "Grilled eel rice bowl with pickles", "food": "うな丼"},
    {"ja": "冷やし中華", "en": "Cold Chinese-style noodles", "food": "冷やし中華"},
    {"ja": "親子丼", "en": "Chicken and egg rice bowl", "food": "親子丼"},
    {"ja": "カレーライス", "en": "Japanese curry rice", "food": "カレーライス"},
    {"ja": "とんかつ定食", "en": "Pork cutlet set meal", "food": "とんかつ"},
    {"ja": "焼き魚定食", "en": "Grilled fish set meal", "food": "焼き魚"},
    {"ja": "納豆ごはん", "en": "Natto over rice", "food": "納豆"},
    {"ja": "茶碗蒸し", "en": "Savory egg custard", "food": "茶碗蒸し"},
    {"ja": "お好み焼きと焼きそば", "en": "Okonomiyaki with yakisoba", "food": "お好み焼き"},
    {"ja": "パスタとフレッシュサラダ", "en": "Pasta with fresh salad", "food": "パスタ"},
    {"ja": "フレンチトーストと珈琲", "en": "French toast with coffee", "food": "フレンチトースト"},
    {"ja": "カレーとガーリックナン", "en": "Curry with garlic naan", "food": "カレー"},
    {"ja": "サンドイッチとスープ", "en": "Sandwich with soup", "food": "サンドイッチ"},
    {"ja": "ピザマルゲリータ", "en": "Margherita pizza", "food": "ピザ"},
    {"ja": "ハンバーグステーキ", "en": "Hamburger steak", "food": "ハンバーグ"},
    {"ja": "グラタンとパン", "en": "Gratin with bread", "food": "グラタン"},
    {"ja": "オムライス", "en": "Omelet rice", "food": "オムライス"},
    {"ja": "シーザーサラダ", "en": "Caesar salad", "food": "シーザーサラダ"},
    {"ja": "リゾット", "en": "Creamy risotto", "food": "リゾット"},
    {"ja": "タコスとサルサ", "en": "Tacos with salsa", "food": "タコス"},
    {"ja": "ベトナムフォー", "en": "Vietnamese pho soup", "food": "フォー"},
    {"ja": "タイカレー", "en": "Thai green curry", "food": "タイカレー"},
    {"ja": "キムチチゲ", "en": "Korean kimchi stew", "food": "チゲ"},
    {"ja": "ビーフン炒め", "en": "Stir-fried rice vermicelli", "food": "ビーフン"},
    {"ja": "サラダボウルとスムージー", "en": "Salad bowl with smoothie", "food": "サラダ"},
    {"ja": "豆腐ステーキ", "en": "Grilled tofu steak", "food": "豆腐"},
    {"ja": "野菜スープ", "en": "Vegetable soup", "food": "野菜スープ"},
    {"ja": "おひたしと納豆", "en": "Blanched spinach with natto", "food": "おひたし"},
    {"ja": "フルーツヨーグルト", "en": "Fruit yogurt", "food": "ヨーグルト"},
    {"ja": "海藻サラダ", "en": "Seaweed salad", "food": "海藻"},
    {"ja": "蒸し野菜", "en": "Steamed vegetables", "food": "蒸し野菜"},
    {"ja": "雑炊", "en": "Japanese rice porridge", "food": "雑炊"},
    {"ja": "春雨サラダ", "en": "Glass noodle salad", "food": "春雨"},
    {"ja": "枝豆と冷奴", "en": "Edamame with chilled tofu", "food": "枝豆"},
    {"ja": "おでん", "en": "Simmered dish", "food": "おでん"},
    {"ja": "すき焼き", "en": "Sukiyaki hot pot", "food": "すき焼き"},
    {"ja": "しゃぶしゃぶ", "en": "Shabu-shabu hot pot", "food": "しゃぶしゃぶ"},
    {"ja": "鍋料理", "en": "Nabe hot pot", "food": "鍋"},
    {"ja": "焼き芋", "en": "Roasted sweet potato", "food": "焼き芋"},
    {"ja": "栗ごはん", "en": "Chestnut rice", "food": "栗ごはん"},
    {"ja": "かぼちゃの煮物", "en": "Simmered pumpkin", "food": "かぼちゃ"},
    {"ja": "大根おろし", "en": "Grated daikon", "food": "大根"},
    {"ja": "お汁粉", "en": "Sweet red bean soup", "food": "お汁粉"},
    {"ja": "ぜんざい", "en": "Zenzai sweet soup", "food": "ぜんざい"},
]


class MealVocab(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        seasonal_palette = get_seasonal_palette(now)
        v = get_variant(device_config.get_config("design_style"), seasonal_palette)

        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        vocab = random.choice(VOCABULARY)
        meal = random.choice(MEALS)
        random.seed()

        food_image = get_food_image(meal.get("food", "寿司"), (300, 200))

        food_image_data_uri = self.image_to_data_uri(food_image)

        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]

            template_params = {
                "palette": seasonal_palette,
                "season_info": season_info,
                "vocab": vocab,
                "meal": meal,
                "food_image": food_image_data_uri,
                "plugin_settings": settings,
                "design_variant": {
                    "name": v.name,
                    "colors": v.colors,
                    "heading_font": v.heading_font,
                    "body_font": v.body_font,
                    "divider_width": v.divider_width,
                },
            }

            image = self.render_image(dimensions_for_render, "meal_vocab.html", "meal_vocab.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, vocab, meal, season_info, settings, now, food_image, v)

    def _draw_card_pil(self, dimensions, orientation, vocab, meal, season_info, settings, now, food_image, v):
        """Elegant 50/50 split with vocab and meal."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg'])
        draw = ImageDraw.Draw(img)

        px = int(w * 0.06 * sm)
        py = int(h * 0.08 * sm)
        mid_x = w // 2

        f_label = get_font(v.body_font, int(w * 0.016))
        f_vocab = get_font(v.body_font, int(w * 0.065))
        f_pron = get_font(v.body_font, int(w * 0.02))
        f_meaning = get_font(v.heading_font, int(w * 0.024))
        f_example = get_font(v.body_font, int(w * 0.018))
        f_meal = get_font(v.heading_font, int(w * 0.032))
        f_meal_desc = get_font(v.body_font, int(w * 0.02))
        f_ms = get_font(v.heading_font, int(w * 0.016))
        f_ms_en = get_font(v.body_font, int(w * 0.012))

        draw.text((px, py), "Palavra do Dia", font=f_label, fill=C['accent'])
        draw.text((px, py + int(h * 0.05 * sm)), vocab["pt"], font=f_vocab, fill=C['accent_alt'])
        draw.text((px, py + int(h * 0.14 * sm)), vocab["ja"], font=f_meaning, fill=C['text_secondary'])
        draw.text((px, py + int(h * 0.2 * sm)), f'"{vocab["example"]}"', font=f_example, fill=C['text_light'])

        draw.line([(mid_x, int(h * 0.1)), (mid_x, int(h * 0.85))], fill=C['divider'], width=v.divider_width)

        rx = mid_x + int(w * 0.05 * sm)
        draw.text((rx, py), "昼食のヒント", font=f_label, fill=C['accent'])
        draw.text((rx, py + int(h * 0.05 * sm)), meal["ja"], font=f_meal, fill=C['text_primary'])
        draw.text((rx, py + int(h * 0.12 * sm)), meal["en"], font=f_meal_desc, fill=C['text_secondary'])

        if food_image:
            ix = rx
            iy = py + int(h * 0.22 * sm)
            iw = int(w * 0.18)
            ih = int(w * 0.18)
            img.paste(food_image.resize((iw, ih), Image.Resampling.LANCZOS), (ix, iy))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ix-2, iy-2, ix+iw+2, iy+ih+2], outline=C['border'], width=v.divider_width)

        if season_info:
            ms_x = w - px
            ms_y = h - int(h * 0.055 * sm)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill=C['accent'])
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.022 * sm)), e, font=f_ms_en, fill=C['text_light'])

        return img
