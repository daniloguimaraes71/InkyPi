import logging
import random
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_seasonal_flower_image
from utils.app_utils import get_font
from utils.design_variants import get_variant
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

FLOWERS = {
    "spring": [
        {"ja": "桜", "en": "Cherry Blossom", "kotoba": "人生の美しさ", "poem": "桜色の\n風が踊る\n春の午後"},
        {"ja": "梅", "en": "Plum Blossom", "kotoba": "高潔", "poem": "梅の香り\n凛と立つ\n寒さの中"},
        {"ja": "藤", "en": "Wisteria", "kotoba": "歓迎", "poem": "藤棚の\n下で交わす\n約束の言葉"},
        {"ja": "菜の花", "en": "Rapeseed Blossom", "kotoba": "活気", "poem": "一面の\n黄色い絨毯\n春の風"},
        {"ja": "桃", "en": "Peach Blossom", "kotoba": "魅力的", "poem": "桃の花\n春の光に\n照らされて"},
        {"ja": "チューリップ", "en": "Tulip", "kotoba": "思いやり", "poem": "色とりどり\nチューリップが\n踊る庭"},
        {"ja": "レンギョウ", "en": "Forsythia", "kotoba": "期待", "poem": "黄金の\n鈴なりに咲く\n春の訪れ"},
        {"ja": "モクレン", "en": "Magnolia", "kotoba": "崇高", "poem": "白大輪\n空に向かって\n凛と咲く"},
        {"ja": "ハナミズキ", "en": "Dogwood", "kotoba": "永続性", "poem": "花水木\n優しく寄り添う\n春の街"},
        {"ja": "パンジー", "en": "Pansy", "kotoba": "思い出", "poem": "可憐に咲く\nパンジーの花に\n春の風"},
        {"ja": "芝桜", "en": "Moss Phlox", "kotoba": "一致", "poem": "地面を\n覆うピンクの\n春の絨毯"},
        {"ja": "スズラン", "en": "Lily of the Valley", "kotoba": "幸福の再来", "poem": "鈴の花\n静かに揺れる\n爽やかな朝"},
        {"ja": "ライラック", "en": "Lilac", "kotoba": "青春", "poem": "薄紫の\n香り立つ風\n春の想い"},
        {"ja": "タンポポ", "en": "Dandelion", "kotoba": "愛の神託", "poem": "綿毛舞う\n野原いっぱい\n春の陽射し"},
        {"ja": "ヒヤシンス", "en": "Hyacinth", "kotoba": "遊び心", "poem": "ヒヤシンス\n甘い香りに\n包まれて"},
        {"ja": "アネモネ", "en": "Anemone", "kotoba": "期待", "poem": "風に揺れ\nアネモネの花\n春を告げる"},
        {"ja": "フリージア", "en": "Freesia", "kotoba": "純潔", "poem": "優しい\n香りを運ぶ\n春風に"},
        {"ja": "アイリス", "en": "Iris", "kotoba": "良き知らせ", "poem": "紫の\nアイリス咲く\n水辺の春"},
        {"ja": "ラナンキュラス", "en": "Ranunculus", "kotoba": "魅力", "poem": "幾重にも\n重なる花びら\n春の華"},
        {"ja": "ミモザ", "en": "Mimosa", "kotoba": "感謝", "poem": "黄色い\n綿のような花\n春の光"},
        {"ja": "芍薬", "en": "Peony", "kotoba": "優雅", "poem": "芍薬の\n大輪の花\n春の誇り"},
        {"ja": "牡丹", "en": "Tree Peony", "kotoba": "富貴", "poem": "百花の王\n牡丹の花は\n春の華"},
        {"ja": "サクラソウ", "en": "Primrose", "kotoba": "初恋", "poem": "可憐な\n桜草の花\n春の朝"},
    ],
    "summer": [
        {"ja": "紫陽花", "en": "Hydrangea", "kotoba": "忍耐", "poem": "紫陽花の\n色変わるたび\n想い馳せ"},
        {"ja": "蓮", "en": "Lotus", "kotoba": "清らか", "poem": "泥の中\n清らかに咲く\n蓮の花"},
        {"ja": "向日葵", "en": "Sunflower", "kotoba": "憧れ", "poem": "太陽を\n見つめて咲く\n向日葵の"},
        {"ja": "朝顔", "en": "Morning Glory", "kotoba": "絆", "poem": "朝顔の\n蔓が絡まる\n君と僕"},
        {"ja": "ユリ", "en": "Lily", "kotoba": "純粋", "poem": "白百合の\n清らかな姿\n夏の庭"},
        {"ja": "バラ", "en": "Rose", "kotoba": "愛情", "poem": "薔薇の花\n情熱の赤\n夏の陽に"},
        {"ja": "ラベンダー", "en": "Lavender", "kotoba": "沈黙", "poem": "紫の\nラベンダー畑\n風香る"},
        {"ja": "ハイビスカス", "en": "Hibiscus", "kotoba": "繊細な美", "poem": "南国の\n太陽の花\n夏の風"},
        {"ja": "ポピー", "en": "Poppy", "kotoba": "思いやり", "poem": "真っ赤な\nポピーの花が\n揺れる野原"},
        {"ja": "カーネーション", "en": "Carnation", "kotoba": "感謝", "poem": "カーネーション\n母への想い\n夏の日に"},
        {"ja": "カスミソウ", "en": "Baby's Breath", "kotoba": "清らかな心", "poem": "霞草\nかすかに揺れる\n夏の風"},
        {"ja": "ペチュニア", "en": "Petunia", "kotoba": "仲良く", "poem": "ペチュニアの\n色とりどりの\n夏の庭"},
        {"ja": "マリーゴールド", "en": "Marigold", "kotoba": "健康", "poem": "黄金の\nマリーゴールド\n夏の日差し"},
        {"ja": "サルビア", "en": "Salvia", "kotoba": "燃える想い", "poem": "赤いサルビア\n夏の陽に\n燃えるように"},
        {"ja": "ジニア", "en": "Zinnia", "kotoba": "友情", "poem": "百日草\n長く楽しめる\n夏の彩り"},
        {"ja": "カンナ", "en": "Canna", "kotoba": "情熱", "poem": "カンナの花\nトロピカルな\n夏の風情"},
        {"ja": "グラジオラス", "en": "Gladiolus", "kotoba": "勝利", "poem": "剣のような\n葉っぱの間から\n夏の花"},
        {"ja": "ルドベキア", "en": "Rudbeckia", "kotoba": "正義", "poem": "黒眼鏡\n太陽に向かって\n夏に咲く"},
        {"ja": "アガパンサス", "en": "Agapanthus", "kotoba": "愛の便り", "poem": "紫の\nアガパンサスが\n風に揺れ"},
        {"ja": "デイジー", "en": "Daisy", "kotoba": "平和", "poem": "デイジーの\n白い花びら\n夏の風"},
        {"ja": "クレマチス", "en": "Clematis", "kotoba": "精神的な美", "poem": "蔓に咲く\nクレマチスの花\n夏の空"},
    ],
    "autumn": [
        {"ja": "紅葉", "en": "Maple", "kotoba": "感謝", "poem": "もみじ葉の\n舞い散る中で\n思い出を"},
        {"ja": "菊", "en": "Chrysanthemum", "kotoba": "高貴", "poem": "菊の香に\n包まれて\n秋の黄昏"},
        {"ja": "秋桜", "en": "Cosmos", "kotoba": "調和", "poem": "秋桜\n風に揺れ\n心落ち着く"},
        {"ja": "萩", "en": "Bush Clover", "kotoba": "想い", "poem": "萩の花\n見れば思い出\nあの日々を"},
        {"ja": "ダリア", "en": "Dahlia", "kotoba": "優雅", "poem": "ダリアの花\n華やかに咲く\n秋の庭"},
        {"ja": "金木犀", "en": "Sweet Osmanthus", "kotoba": "謙虚", "poem": "金木犀\n香る小道を\n歩く秋"},
        {"ja": "ススキ", "en": "Pampas Grass", "kotoba": "活力", "poem": "ススキの穂\n風に揺れている\n秋の空"},
        {"ja": "リンドウ", "en": "Gentian", "kotoba": "正義", "poem": "竜胆の\n青紫の花\n秋の山"},
        {"ja": "ガーベラ", "en": "Gerbera", "kotoba": "希望", "poem": "ガーベラの\n明るい色が\n秋を彩る"},
        {"ja": "曼珠沙華", "en": "Spider Lily", "kotoba": "悲しい思い出", "poem": "真紅の\n曼珠沙華が\n秋を告げる"},
        {"ja": "ケイトウ", "en": "Cockscomb", "kotoba": "おしゃれ", "poem": "鶏頭の\n赤い花穂が\n秋の陽に"},
        {"ja": "ホトトギス", "en": "Toad Lily", "kotoba": "永遠", "poem": "杜鵑草\n紫の斑点\n秋の林"},
        {"ja": "シクラメン", "en": "Cyclamen", "kotoba": "はにかみ", "poem": "シクラメン\nうつむく姿が\n秋の風情"},
        {"ja": "ワレモコウ", "en": "Burnet", "kotoba": "変化", "poem": "吾木香\n秋の野原に\nひっそりと"},
        {"ja": "サルビア", "en": "Scarlet Sage", "kotoba": "家族愛", "poem": "秋の日の\nサルビア赤く\n庭を彩る"},
        {"ja": "パンパスグラス", "en": "Pampas Grass", "kotoba": "雄大", "poem": "パンパスの\n大きな穂が\n秋風に"},
        {"ja": "コルチカム", "en": "Autumn Crocus", "kotoba": "青春の後悔", "poem": "秋の日の\nコルチカム咲く\n静けさに"},
    ],
    "winter": [
        {"ja": "椿", "en": "Camellia", "kotoba": "誇り", "poem": "椿の花\n静かに咲く\n冬の庭"},
        {"ja": "水仙", "en": "Narcissus", "kotoba": "自己愛", "poem": "水仙の\n凛とした姿\n冬の陽に"},
        {"ja": "山茶花", "en": "Sasanqua", "kotoba": "困難に打ち勝つ", "poem": "寒さにも\n負けず咲く\n山茶花の"},
        {"ja": "梅", "en": "Plum Blossom", "kotoba": "希望", "poem": "雪の中\n香り立つ\n梅の花"},
        {"ja": "シクラメン", "en": "Cyclamen", "kotoba": "祝福", "poem": "冬の陽に\nシクラメンの花\n温もりを"},
        {"ja": "ポインセチア", "en": "Poinsettia", "kotoba": "祝福", "poem": "赤い苞が\nクリスマスを\n告げている"},
        {"ja": "クリスマスローズ", "en": "Christmas Rose", "kotoba": "追憶", "poem": "雪の中\nひっそり咲く\n冬のバラ"},
        {"ja": "スノードロップ", "en": "Snowdrop", "kotoba": "希望", "poem": "雪の下\n顔を出す白い\n春の予感"},
        {"ja": "ローズマリー", "en": "Rosemary", "kotoba": "追憶", "poem": "ローズマリー\n香り立つ冬\n思い出の中"},
        {"ja": "オリーブ", "en": "Olive", "kotoba": "平和", "poem": "銀色の\n葉が揺れる\n冬の庭"},
        {"ja": "ユーカリ", "en": "Eucalyptus", "kotoba": "新生", "poem": "爽やかな\n香りのユーカリ\n冬の朝"},
        {"ja": "エーデルワイス", "en": "Edelweiss", "kotoba": "勇気", "poem": "雪の花\nエーデルワイス\n凛と咲く"},
        {"ja": "蝋梅", "en": "Wintersweet", "kotoba": "慈愛", "poem": "蝋梅の\n透き通る花\n冬の庭"},
        {"ja": "寒椿", "en": "Winter Camellia", "kotoba": "愛嬌", "poem": "寒椿\n雪をかぶって\n赤く咲く"},
        {"ja": "松", "en": "Pine", "kotoba": "不老長寿", "poem": "冬の松\n雪をかぶっても\n緑のまま"},
    ],
}

MOODS = [
    {"ja": "今日は穏やかな気持ちで過ごせそうです。", "en": "A calm and peaceful day awaits you."},
    {"ja": "小さな幸せに気づく一日を。", "en": "Notice the small happiness today."},
    {"ja": "心を開いて、新しい出会いを。", "en": "Open your heart to new encounters."},
    {"ja": "自分を信じて、一歩前に。", "en": "Believe in yourself, take one step forward."},
    {"ja": "今日のあなたに、花を添えます。", "en": "Adding a flower to your day."},
    {"ja": "静かなる情熱を持って。", "en": "With quiet passion."},
    {"ja": "風のままに、流れるままに。", "en": "Go with the wind, flow with life."},
    {"ja": "感謝の気持ちを忘れずに。", "en": "Never forget gratitude."},
    {"ja": "今日も笑顔で、素敵な日に。", "en": "With a smile, make today wonderful."},
    {"ja": "自分らしく、あるがままに。", "en": "Be yourself, just as you are."},
]


class MoodCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        seasonal_palette = get_seasonal_palette(now)
        v = get_variant(device_config.get_config("design_style"), seasonal_palette)

        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        seasonal_flowers = FLOWERS.get(season, FLOWERS["spring"])
        candidates = [f for f in seasonal_flowers if f["ja"] != getattr(self, "_last_flower", None)]
        if not candidates:
            candidates = seasonal_flowers
        flower = random.choice(candidates)
        self._last_flower = flower["ja"]
        mood = random.choice(MOODS)

        flower_image = get_seasonal_flower_image(flower["ja"], (224, 304))

        flower_image_data_uri = self.image_to_data_uri(flower_image)

        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]

            template_params = {
                "palette": seasonal_palette,
                "season_info": season_info,
                "flower": flower,
                "mood": mood,
                "flower_image": flower_image_data_uri,
                "plugin_settings": settings,
                "design_variant": {
                    "name": v.name,
                    "colors": v.colors,
                    "heading_font": v.heading_font,
                    "body_font": v.body_font,
                    "divider_width": v.divider_width,
                },
            }

            image = self.render_image(dimensions_for_render, "mood_card.html", "mood_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, flower, mood, season_info, settings, now, flower_image, v)

    def _draw_card_pil(self, dimensions, orientation, flower, mood, season_info, settings, now, flower_image, v):
        """Elegant flower + mood card with photo frame."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg'])
        draw = ImageDraw.Draw(img)

        px = int(w * 0.05 * sm)
        py = int(h * 0.07 * sm)
        photo_w = int(w * 0.28)
        photo_h = h - py * 2
        gap = int(w * 0.05 * sm)
        text_x = px + photo_w + gap

        f_flower = get_font(v.heading_font, int(w * 0.07))
        f_en = get_font(v.heading_font, int(w * 0.028))
        f_kotoba = get_font(v.body_font, int(w * 0.02))
        f_mood = get_font(v.heading_font, int(w * 0.024))
        f_mood_en = get_font(v.body_font, int(w * 0.018))
        f_poem = get_font(v.heading_font, int(w * 0.016))
        f_ms = get_font(v.heading_font, int(w * 0.016))
        f_ms_en = get_font(v.body_font, int(w * 0.012))

        if flower_image:
            img.paste(flower_image.resize((photo_w, photo_h), Image.Resampling.LANCZOS), (px, py))
            draw = ImageDraw.Draw(img)
            draw.rectangle([px-2, py-2, px+photo_w+2, py+photo_h+2], outline=C['border'], width=v.divider_width)
        else:
            draw.rectangle([px, py, px+photo_w, py+photo_h], fill=C['border'], outline=C['border'], width=1)
            bbox = draw.textbbox((0, 0), flower["ja"], font=f_flower)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((px + (photo_w - tw) // 2, py + (photo_h - th) // 2), flower["ja"], font=f_flower, fill=C['text_light'])

        draw.text((text_x, py), flower["ja"], font=f_flower, fill=C['text_primary'])
        draw.text((text_x, py + int(h * 0.1 * sm)), flower["en"], font=f_en, fill=C['text_secondary'])

        ky_y = py + int(h * 0.18 * sm)
        draw.line([(text_x, ky_y), (text_x + 3, ky_y + int(h * 0.06 * sm))], fill=C['accent_alt'], width=v.divider_width + 1)
        draw.text((text_x + int(w * 0.02), ky_y), f"花言葉: {flower['kotoba']}", font=f_kotoba, fill=C['accent'])

        div_y = ky_y + int(h * 0.08 * sm)
        draw.line([(text_x, div_y), (text_x + int(w * 0.35), div_y)], fill=C['divider'], width=v.divider_width)

        my = div_y + int(h * 0.05 * sm)
        draw.text((text_x, my), mood["ja"], font=f_mood, fill=C['text_primary'])
        draw.text((text_x, my + int(h * 0.04 * sm)), mood["en"], font=f_mood_en, fill=C['text_secondary'])

        if flower.get("poem"):
            draw.text((text_x, my + int(h * 0.1 * sm)), flower["poem"], font=f_poem, fill=C['text_light'])

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
