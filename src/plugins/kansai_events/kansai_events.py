import logging
import random
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_kansai_location_image
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Curated Kansai events with Wikipedia search terms
EVENTS = {
    "spring": [
        {"name": "お花見ピクニック", "location": "大阪城公園", "type": "花見", "desc": "Cherry blossom viewing picnic", "wiki": "大阪城"},
        {"name": "奈良公園の鹿と散歩", "location": "奈良", "type": "アウトドア", "desc": "Walk with deer in Nara Park", "wiki": "奈良公園"},
        {"name": "清水寺と祇園散策", "location": "京都", "type": "観光", "desc": "Kiyomizdera & Gion walk", "wiki": "清水寺"},
        {"name": "箕面の滝ハイキング", "location": "箕面", "type": "ハイキング", "desc": "Minoh waterfall hike", "wiki": "箕面"},
    ],
    "summer": [
        {"name": "天神祭りの花火", "location": "大阪", "type": "祭り", "desc": "Tenjin Matsuri fireworks", "wiki": "天神祭"},
        {"name": "須磨海水浴場", "location": "神戸", "type": "ビーチ", "desc": "Suma Beach day", "wiki": "須磨海水浴場"},
        {"name": "有馬温泉でリフレッシュ", "location": "神戸", "type": "温泉", "desc": "Arima Onsen refresh", "wiki": "有馬温泉"},
        {"name": "梅田スカイビルの夜景", "location": "大阪", "type": "観光", "desc": "Umeda Sky Building night view", "wiki": "梅田スカイビル"},
    ],
    "autumn": [
        {"name": "紅葉狩り", "location": "京都", "type": "紅葉", "desc": "Autumn leaf viewing", "wiki": "京都"},
        {"name": "伏見稲荷大社", "location": "京都", "type": "観光", "desc": "Fushimi Inari shrine", "wiki": "伏見稲荷大社"},
        {"name": "神戸ルミナリー", "location": "神戸", "type": "イベント", "desc": "Kobe Luminarie", "wiki": "神戸ルミナリー"},
        {"name": "姫路城と日本庭園", "location": "姫路", "type": "観光", "desc": "Himeji Castle & garden", "wiki": "姫路城"},
    ],
    "winter": [
        {"name": "奈良のイルミネーション", "location": "奈良", "type": "イルミネーション", "desc": "Nara illumination", "wiki": "奈良公園"},
        {"name": "大阪クリスマスマーケット", "location": "大阪", "type": "マーケット", "desc": "Osaka Christmas Market", "wiki": "大阪"},
        {"name": "神戸の光のルナリエ", "location": "神戸", "type": "イルミネーション", "desc": "Kobe Luminarie", "wiki": "神戸ルミナリー"},
        {"name": "有馬温泉日帰り旅行", "location": "有馬", "type": "温泉", "desc": "Arima Onsen day trip", "wiki": "有馬温泉"},
    ],
}


class KansaiEvents(BasePlugin):
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

        # Pick event based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        events = EVENTS.get(season, EVENTS["spring"])
        event = random.choice(events)
        random.seed()

        # Find next weekend
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            days_until_saturday = 0
        weekend_start = now.date() + timedelta(days=days_until_saturday)
        weekend_date = f"{weekend_start.strftime('%m月%d日')} Weekend"

        # Get location image from Wikipedia
        event_image = get_kansai_location_image(event.get("wiki", event["location"]), (350, 400))
        
        # Save image to temporary file for HTML rendering
        event_image_url = None
        if event_image:
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp') as f:
                event_image.save(f, 'PNG')
                event_image_url = f'file://{f.name}'

        # Try HTML render first, fall back to PIL
        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "event": event,
                "event_image": event_image_url,
                "weekend_date": weekend_date,
                "season_label": f"{season_info['micro_season']['kanji']} - {season_info['micro_season']['english']}" if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "kansai_events.html", "kansai_events.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL rendering
        return self._draw_card_pil(dimensions, orientation, event, season_info, palette, settings, now, weekend_date, event_image)

    def _draw_card_pil(self, dimensions, orientation, event, season_info, palette, settings, now, weekend_date, event_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Create base image
        bg_color = '#FAF8F5'
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Fonts
        font_title = get_font("Noto Serif JP", int(w * 0.06))
        font_desc = get_font("Noto Sans JP", int(w * 0.035))
        font_info = get_font("Noto Sans JP", int(w * 0.03))
        font_label = get_font("Noto Sans JP", int(w * 0.025))

        # Photo area
        if event_image:
            photo_x, photo_y = int(w * 0.04), int(h * 0.1)
            photo_w, photo_h = int(w * 0.4), int(h * 0.8)
            
            # Resize and paste
            photo_resized = event_image.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (photo_x, photo_y))
            
            # Add border
            draw = ImageDraw.Draw(img)
            draw.rectangle([photo_x-2, photo_y-2, photo_x+photo_w+2, photo_y+photo_h+2], 
                          outline='#E0D8C8', width=2)
            
            text_x = photo_x + photo_w + int(w * 0.06)
        else:
            text_x = int(w * 0.08)

        # Weekend label
        draw.text((text_x, int(h * 0.15)), weekend_date, font=font_label, fill='#999999')
        
        # Event tag
        draw.text((text_x, int(h * 0.22)), f"週末のおすすめ • {event['type']}", font=font_label, fill='#8B7355')
        
        # Event title
        draw.text((text_x, int(h * 0.3)), event["name"], font=font_title, fill='#2C2C2C')
        
        # Description
        draw.text((text_x, int(h * 0.45)), event["desc"], font=font_desc, fill='#666666')
        
        # Location
        draw.text((text_x, int(h * 0.55)), f"場所: {event['location']}", font=font_info, fill='#666666')

        return img
