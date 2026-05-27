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
    ],
    "summer": [
        {"ja": "紫陽花", "en": "Hydrangea", "kotoba": "忍耐", "poem": "紫陽花の\n色変わるたび\n想い馳せ"},
        {"ja": "蓮", "en": "Lotus", "kotoba": "清らか", "poem": "泥の中\n清らかに咲く\n蓮の花"},
        {"ja": "向日葵", "en": "Sunflower", "kotoba": "憧れ", "poem": "太陽を\n見つめて咲く\n向日葵の"},
        {"ja": "朝顔", "en": "Morning Glory", "kotoba": "絆", "poem": "朝顔の\n蔓が絡まる\n君と僕"},
    ],
    "autumn": [
        {"ja": "紅葉", "en": "Maple", "kotoba": "感謝", "poem": "もみじ葉の\n舞い散る中で\n思い出を"},
        {"ja": "菊", "en": "Chrysanthemum", "kotoba": "高貴", "poem": "菊の香に\n包まれて\n秋の黄昏"},
        {"ja": "秋桜", "en": "Cosmos", "kotoba": "調和", "poem": "秋桜\n風に揺れ\n心落ち着く"},
        {"ja": "萩", "en": "Bush Clover", "kotoba": "想い", "poem": "萩の花\n見れば思い出\nあの日々を"},
    ],
    "winter": [
        {"ja": "椿", "en": "Camellia", "kotoba": "誇り", "poem": "椿の花\n静かに咲く\n冬の庭"},
        {"ja": "水仙", "en": "Narcissus", "kotoba": "自己愛", "poem": "水仙の\n凛とした姿\n冬の陽に"},
        {"ja": "山茶花", "en": "Sasanqua", "kotoba": "困難に打ち勝つ", "poem": "寒さにも\n負けず咲く\n山茶花の"},
        {"ja": "梅", "en": "Plum Blossom", "kotoba": "希望", "poem": "雪の中\n香り立つ\n梅の花"},
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
        flower = random.choice(seasonal_flowers)
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
