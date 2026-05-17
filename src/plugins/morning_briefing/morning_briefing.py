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

# Morning-related Wikipedia images
MORNING_IMAGES = {
    "spring": "Cherry_blossom",
    "summer": "Sunrise",
    "autumn": "Maple",
    "winter": "Snow",
}


class MorningBriefing(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        time_format = device_config.get_config("time_format", default="24h")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)
        weather_data = self._get_weather_summary(device_config, tz)
        calendar_events = self._get_calendar_events(settings, device_config, tz, now)

        # Get seasonal morning image
        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"
        
        image_keyword = MORNING_IMAGES.get(season, "Sunrise")
        morning_image = get_wikipedia_image(image_keyword, (280, 350))
        
        # Save image for HTML rendering
        image_url = None
        if morning_image:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir='/tmp') as f:
                morning_image.save(f, 'PNG')
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
                "weather": weather_data,
                "events": calendar_events,
                "morning_image": image_url,
                "image_label": season_info['micro_season']['kanji'] if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "morning_briefing.html", "morning_briefing.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        # Fallback to PIL
        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, 
                                   weather_data, calendar_events, time_format, morning_image)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, 
                       weather, events, time_format, morning_image):
        """Fallback PIL rendering."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        bg_color = palette.get('bg', '#FAF8F5')
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        font_greeting = get_font("Noto Serif JP", int(w * 0.08))
        font_date = get_font("Noto Sans JP", int(w * 0.035))
        font_weather = get_font("Noto Serif JP", int(w * 0.06))
        font_event = get_font("Noto Sans JP", int(w * 0.03))
        font_small = get_font("Noto Sans JP", int(w * 0.025))

        left_x = int(w * 0.06)

        # Morning image
        if morning_image:
            img_x, img_y = int(w * 0.55), int(h * 0.1)
            img_w, img_h = int(w * 0.38), int(h * 0.75)
            photo_resized = morning_image.resize((img_w, img_h), Image.Resampling.LANCZOS)
            img.paste(photo_resized, (img_x, img_y))
            draw = ImageDraw.Draw(img)
            draw.rectangle([img_x-1, img_y-1, img_x+img_w+1, img_y+img_h+1], outline='#E0D8C8', width=1)

        # Greeting
        draw.text((left_x, int(h * 0.12)), "おはようございます", font=font_greeting, fill='#2C2C2C')
        draw.text((left_x, int(h * 0.24)), now.strftime("%Y年%m月%d日 %A"), font=font_date, fill='#666666')

        # Weather
        if weather:
            draw.text((left_x, int(h * 0.38)), f"{weather['temp']}°C", font=font_weather, fill='#2C2C2C')
            draw.text((left_x + int(w * 0.15), int(h * 0.42)), weather['description'], font=font_small, fill='#666666')

        # Events
        if events:
            event_y = int(h * 0.58)
            draw.text((left_x, event_y - int(h * 0.03)), "今日の予定", font=font_small, fill='#8B7355')
            for event in events[:3]:
                draw.text((left_x, event_y), event['time'], font=font_small, fill='#999999')
                draw.text((left_x + int(w * 0.1), event_y), event['title'], font=font_event, fill='#2C2C2C')
                event_y += int(h * 0.06)

        # Micro-season
        if season_info:
            draw.text((left_x, int(h * 0.9)), f"時候: {season_info['micro_season']['kanji']}", font=font_small, fill='#8B7355')

        return img

    def _get_weather_summary(self, device_config, tz):
        try:
            api_key = device_config.load_env_key("OPEN_WEATHER_MAP_SECRET")
            if not api_key:
                return None
            lat = device_config.get_config("latitude", default=None)
            lon = device_config.get_config("longitude", default=None)
            if not lat or not lon:
                return None
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "temp": round(data["main"]["temp"]),
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
            }
        except Exception as e:
            logger.warning(f"Failed to fetch weather: {e}")
            return None

    def _get_calendar_events(self, settings, device_config, tz, now):
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
            start = datetime(now.year, now.month, now.day)
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
            return parsed[:8]
        except Exception as e:
            logger.warning(f"Failed to fetch calendar: {e}")
            return []
