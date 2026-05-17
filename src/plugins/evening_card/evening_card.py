import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_wikipedia_image
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)

# Evening-related Wikipedia images
EVENING_IMAGES = {
    "spring": "Hanami",
    "summer": "Sunset",
    "autumn": "Momiji",
    "winter": "Hot_spring",
}


class EveningCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        time_format = device_config.get_config("time_format", default="24h")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)
        tomorrow_weather = self._get_tomorrow_weather(device_config, tz, now)
        tomorrow_events = self._get_tomorrow_events(settings, device_config, tz, now)

        # Get seasonal evening image
        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"
        
        image_keyword = EVENING_IMAGES.get(season, "Sunset")
        evening_image = get_wikipedia_image(image_keyword, (280, 350))
        
        # Save image for HTML rendering
        image_url = None
        if evening_image:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp') as f:
                evening_image.save(f, 'PNG')
                image_url = f'file://{f.name}'

        # Try HTML render
        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "now": now,
                "time_format": time_format,
                "weather": tomorrow_weather,
                "events": tomorrow_events,
                "evening_image": image_url,
                "image_label": season_info['micro_season']['kanji'] if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "evening_card.html", "evening_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL
        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, 
                                   tomorrow_weather, tomorrow_events, time_format, evening_image)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, 
                       weather, events, time_format, evening_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        bg_color = palette.get('bg', '#FAF8F5')
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        font_greeting = get_font("Noto Serif JP", int(w * 0.08))
        font_subtitle = get_font("Noto Sans JP", int(w * 0.035))
        font_weather = get_font("Noto Serif JP", int(w * 0.05))
        font_event = get_font("Noto Sans JP", int(w * 0.03))
        font_small = get_font("Noto Sans JP", int(w * 0.025))

        left_x = int(w * 0.06)

        # Evening image
        if evening_image:
            img_x, img_y = int(w * 0.55), int(h * 0.1)
            img_w, img_h = int(w * 0.38), int(h * 0.75)
            photo_resized = evening_image.resize((img_w, img_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (img_x, img_y))
            draw = ImageDraw.Draw(img)
            draw.rectangle([img_x-1, img_y-1, img_x+img_w+1, img_y+img_h+1], outline='#E0D8C8', width=1)

        # Greeting
        draw.text((left_x, int(h * 0.12)), "今晩は", font=font_greeting, fill='#2C2C2C')
        draw.text((left_x, int(h * 0.22)), "Good Evening", font=font_subtitle, fill='#666666')

        # Tomorrow's weather
        if weather:
            draw.text((left_x, int(h * 0.38)), "明日の天気", font=font_small, fill='#8B7355')
            draw.text((left_x, int(h * 0.45)), f"{weather['high']}° / {weather['low']}°", font=font_weather, fill='#2C2C2C')
            draw.text((left_x + int(w * 0.2), int(h * 0.48)), weather['description'], font=font_subtitle, fill='#666666')

        # Tomorrow's events
        if events:
            event_y = int(h * 0.62)
            draw.text((left_x, event_y - int(h * 0.03)), "明日の予定", font=font_small, fill='#8B7355')
            for event in events[:3]:
                draw.text((left_x, event_y), event['time'], font=font_small, fill='#999999')
                draw.text((left_x + int(w * 0.1), event_y), event['title'], font=font_event, fill='#2C2C2C')
                event_y += int(h * 0.06)

        # Micro-season
        if season_info:
            draw.text((left_x, int(h * 0.9)), f"時候: {season_info['micro_season']['kanji']}", font=font_small, fill='#8B7355')

        return img

    def _get_tomorrow_weather(self, device_config, tz, now):
        try:
            api_key = device_config.load_env_key("OPEN_WEATHER_MAP_SECRET")
            if not api_key:
                return None
            lat = device_config.get_config("latitude", default=None)
            lon = device_config.get_config("longitude", default=None)
            if not lat or not lon:
                return None
            url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&cnt=8&appid={api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            tomorrow = now.date() + timedelta(days=1)
            tomorrow_items = [
                item for item in data.get("list", [])
                if datetime.fromtimestamp(item["dt"], tz=tz).date() == tomorrow
            ]
            if not tomorrow_items:
                return None
            temps = [item["main"]["temp"] for item in tomorrow_items]
            descriptions = [item["weather"][0]["description"] for item in tomorrow_items]
            most_common = max(set(descriptions), key=descriptions.count)
            return {
                "high": round(max(temps)),
                "low": round(min(temps)),
                "description": most_common,
            }
        except Exception as e:
            logger.warning(f"Failed to fetch tomorrow weather: {e}")
            return None

    def _get_tomorrow_events(self, settings, device_config, tz, now):
        calendar_url = settings.get("calendarURL")
        if not calendar_url:
            return []
        try:
            import icalendar
            import recurring_ical_events
            if calendar_url.startswith("webcal://"):
                calendar_url = calendar_url.replace("webcal://", "https://")
            resp = requests.get(calendar_url, timeout=15)
            resp.raise_for_status()
            cal = icalendar.Calendar.from_ical(resp.text)
            tomorrow = now.date() + timedelta(days=1)
            start = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
            end = start + timedelta(days=1)
            events = recurring_ical_events.of(cal).between(start, end)
            parsed = []
            for event in events:
                dtstart = event.decoded("dtstart")
                if isinstance(dtstart, datetime):
                    dtstart = dtstart.astimezone(tz)
                parsed.append({
                    "title": str(event.get("summary", "")),
                    "time": dtstart.strftime("%H:%M") if isinstance(dtstart, datetime) else "All day",
                })
            parsed.sort(key=lambda e: e["time"])
            return parsed[:6]
        except Exception as e:
            logger.warning(f"Failed to fetch calendar: {e}")
            return []
