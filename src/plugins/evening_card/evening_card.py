import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class EveningCard(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        time_format = device_config.get_config("time_format", default="24h")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)
        tomorrow_weather = self._get_tomorrow_weather(device_config, tz, now)
        tomorrow_events = self._get_tomorrow_events(settings, device_config, tz, now)

        return self._draw_card(dimensions, now, season_info, palette, tomorrow_weather, tomorrow_events, settings, time_format)

    def _draw_card(self, dimensions, now, season_info, palette, weather, events, settings, time_format):
        w, h = dimensions
        
        # Elegant background
        bg_color = ImageColor.getcolor(settings.get("backgroundColor", "#FAFAF8"), "RGB")
        img = Image.new("RGBA", dimensions, bg_color + (255,))
        draw = ImageDraw.Draw(img)

        primary = ImageColor.getcolor(settings.get("textColor", "#2C2C2C"), "RGB")
        accent = ImageColor.getcolor(palette.get("accent", "#8B7355"), "RGB")
        secondary = ImageColor.getcolor(palette.get("secondary", "#C4B99C"), "RGB")

        # Fonts
        font_greeting = get_font("Noto Serif JP", int(w * 0.08))
        font_subtitle = get_font("Noto Sans JP", int(w * 0.035))
        font_weather = get_font("Noto Serif JP", int(w * 0.05))
        font_event = get_font("Noto Sans JP", int(w * 0.032))
        font_small = get_font("Noto Sans JP", int(w * 0.028))

        left_x = int(w * 0.08)
        
        # Greeting - elegant Japanese
        draw.text((left_x, int(h * 0.12)), "今晩は", font=font_greeting, fill=primary)
        draw.text((left_x, int(h * 0.22)), "Good Evening", font=font_subtitle, fill=primary + (180,))

        # Subtle divider
        draw.line([(left_x, int(h * 0.30)), (w - left_x, int(h * 0.30))], fill=secondary + (80,), width=1)

        # Tomorrow's weather
        if weather:
            draw.text((left_x, int(h * 0.35)), "明日の天気", font=font_small, fill=accent)
            draw.text((left_x, int(h * 0.42)), f"{weather['high']}° / {weather['low']}°", font=font_weather, fill=primary)
            draw.text((left_x + int(w * 0.2), int(h * 0.45)), weather['description'], font=font_subtitle, fill=primary + (180,))

        # Tomorrow's events
        if events:
            event_y = int(h * 0.58)
            draw.text((left_x, event_y - int(h * 0.04)), "明日の予定", font=font_small, fill=accent)
            
            for event in events[:3]:
                time_str = event['time']
                title = event['title']
                draw.text((left_x, event_y), time_str, font=font_small, fill=primary + (150,))
                draw.text((left_x + int(w * 0.1), event_y), title, font=font_event, fill=primary)
                event_y += int(h * 0.06)

        # Footer - Season context
        footer_y = int(h * 0.85)
        draw.line([(left_x, footer_y), (w - left_x, footer_y)], fill=secondary + (60,), width=1)
        
        # Date
        date_str = now.strftime("%Y年%m月%d日")
        draw.text((left_x, footer_y + int(h * 0.03)), date_str, font=font_small, fill=primary + (150,))
        
        # Micro-season with context
        if season_info:
            season_label = f"時候: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            draw.text((w - left_x, footer_y + int(h * 0.03)), season_label, font=font_small, fill=accent, anchor="rt")
            draw.text((w - left_x, footer_y + int(h * 0.07)), season_meaning, font=font_small, fill=primary + (120,), anchor="rt")

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
                "date": tomorrow.strftime("%A, %B %d"),
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
                    "all_day": not isinstance(dtstart, datetime),
                })

            parsed.sort(key=lambda e: (e["all_day"], e["time"]))
            return parsed[:6]

        except Exception as e:
            logger.warning(f"Failed to fetch calendar for evening card: {e}")
            return []
