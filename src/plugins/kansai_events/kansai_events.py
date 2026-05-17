import logging
import random
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.card_design import CardDesign, ImageLoader, wrap_text
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor, ImageOps

logger = logging.getLogger(__name__)

# Curated Kansai events with photo search queries
EVENTS = {
    "spring": [
        {"name": "お花見ピクニック", "location": "大阪城公園", "type": "花見", "desc": "Cherry blossom viewing picnic", "photo_query": "osaka castle cherry blossom"},
        {"name": "奈良公園の鹿と散歩", "location": "奈良", "type": "アウトドア", "desc": "Walk with deer in Nara Park", "photo_query": "nara park deer"},
        {"name": "清水寺と祇園散策", "location": "京都", "type": "観光", "desc": "Kiyomizdera & Gion walk", "photo_query": "kiyomizdera temple kyoto"},
        {"name": "箕面の滝ハイキング", "location": "箕面", "type": "ハイキング", "desc": "Minoh waterfall hike", "photo_query": "minoh waterfall"},
    ],
    "summer": [
        {"name": "天神祭りの花火", "location": "大阪", "type": "祭り", "desc": "Tenjin Matsuri fireworks", "photo_query": "tenjin matsuri fireworks"},
        {"name": "須磨海水浴場", "location": "神戸", "type": "ビーチ", "desc": "Suma Beach day", "photo_query": "suma beach kobe"},
        {"name": "有馬温泉でリフレッシュ", "location": "神戸", "type": "温泉", "desc": "Arima Onsen refresh", "photo_query": "arima onsen"},
        {"name": "梅田スカイビルの夜景", "location": "大阪", "type": "観光", "desc": "Umeda Sky Building night view", "photo_query": "umeda sky building"},
    ],
    "autumn": [
        {"name": "紅葉狩り", "location": "京都", "type": "紅葉", "desc": "Autumn leaf viewing", "photo_query": "kyoto autumn leaves"},
        {"name": "伏見稲荷大社", "location": "京都", "type": "観光", "desc": "Fushimi Inari shrine", "photo_query": "fushimi inari shrine"},
        {"name": "神戸ルミナリー", "location": "神戸", "type": "イベント", "desc": "Kobe Luminarie", "photo_query": "kobe luminarie"},
        {"name": "姫路城と日本庭園", "location": "姫路", "type": "観光", "desc": "Himeji Castle & garden", "photo_query": "himeji castle"},
    ],
    "winter": [
        {"name": "奈良のイルミネーション", "location": "奈良", "type": "イルミネーション", "desc": "Nara illumination", "photo_query": "nara illumination"},
        {"name": "大阪クリスマスマーケット", "location": "大阪", "type": "マーケット", "desc": "Osaka Christmas Market", "photo_query": "osaka christmas market"},
        {"name": "神戸の光のルナリエ", "location": "神戸", "type": "イルミネーション", "desc": "Kobe Luminarie", "photo_query": "kobe luminarie lights"},
        {"name": "有馬温泉日帰り旅行", "location": "有馬", "type": "温泉", "desc": "Arima Onsen day trip", "photo_query": "arima onsen winter"},
    ],
}

# Fallback photo URLs (curated Kansai photos)
FALLBACK_PHOTOS = {
    "spring": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=800",
    "summer": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=800",
    "autumn": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800",
    "winter": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=800",
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

        # Pick events based on date
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        events = random.sample(EVENTS.get(season, []), min(3, len(EVENTS.get(season, []))))
        random.seed()

        # Find next weekend
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            days_until_saturday = 0
        weekend_start = now.date() + timedelta(days=days_until_saturday)

        # Try to load a photo for the first event
        photo = self._load_event_photo(events[0] if events else None, season, dimensions)

        return self._draw_card(dimensions, orientation, events, season_info, palette, 
                              settings, now, weekend_start, season, photo)

    def _load_event_photo(self, event, season, dimensions):
        """Load a photo for the event."""
        try:
            # Try Unsplash API (if available)
            query = event.get("photo_query", f"kansai {season}") if event else f"kansai {season}"
            
            # Use a curated photo URL based on query
            # For now, use fallback photos
            photo_url = FALLBACK_PHOTOS.get(season, FALLBACK_PHOTOS["spring"])
            
            target_size = (int(dimensions[0] * 0.4), int(dimensions[1] * 0.6))
            return ImageLoader.load_and_fit(photo_url, target_size)
            
        except Exception as e:
            logger.warning(f"Failed to load event photo: {e}")
            return None

    def _draw_card(self, dimensions, orientation, events, season_info, palette, 
                   settings, now, weekend_start, season, photo):
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Initialize design system
        design = CardDesign((w, h), orientation)
        
        # Create base card
        img = design.create_base_card(palette=palette)
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = design.draw_header(draw, "週末のおでかけ", 
                                  f"{weekend_start.strftime('%m月%d日')} Weekend")

        # Photo section (if available)
        if photo:
            photo_x = design.margin
            photo_y = y_pos
            photo_w = int(w * 0.35)
            photo_h = int(h * 0.45)
            
            # Paste photo with elegant border
            photo_resized = photo.resize((photo_w, photo_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (photo_x, photo_y))
            
            # Add subtle border
            draw = ImageDraw.Draw(img)
            draw.rectangle([photo_x-1, photo_y-1, photo_x+photo_w+1, photo_y+photo_h+1], 
                          outline=design.COLORS['divider'], width=1)
            
            # Events list on the right
            events_x = photo_x + photo_w + int(w * 0.04)
            events_w = w - events_x - design.margin
        else:
            # Full width events
            events_x = design.margin
            events_w = w - 2 * design.margin
            photo_w = 0

        # Events list
        event_y = y_pos + int(h * 0.05)
        for i, event in enumerate(events):
            # Event number
            design.draw_card_number(draw, i + 1, events_x + int(w * 0.02), event_y + int(h * 0.02))
            
            # Event name
            draw.text((events_x + int(w * 0.06), event_y), 
                     event["name"], font=design.fonts['h3'], fill=design.COLORS['text_primary'])
            
            # Location and type
            loc_text = f"{event['location']} · {event['type']}"
            draw.text((events_x + int(w * 0.06), event_y + int(h * 0.04)), 
                     loc_text, font=design.fonts['caption'], fill=design.COLORS['text_secondary'])
            
            # Description
            draw.text((events_x + int(w * 0.06), event_y + int(h * 0.07)), 
                     event["desc"], font=design.fonts['micro'], fill=design.COLORS['text_light'])
            
            event_y += int(h * 0.18)

        # Footer - no micro-season
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info, show_season=False)

        return img
