import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class MorningBriefing(BasePlugin):
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
        weather_data = self._get_weather_summary(device_config, tz)
        calendar_events = self._get_calendar_events(settings, device_config, tz, now)

        return self._draw_card(dimensions, now, season_info, palette, weather_data, calendar_events, settings, time_format)

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
        font_date = get_font("Noto Sans JP", int(w * 0.035))
        font_weather_temp = get_font("Noto Serif JP", int(w * 0.06))
        font_weather_desc = get_font("Noto Sans JP", int(w * 0.03))
        font_event = get_font("Noto Sans JP", int(w * 0.032))
        font_small = get_font("Noto Sans JP", int(w * 0.028))

        left_x = int(w * 0.08)
        
        # Greeting - elegant Japanese
        draw.text((left_x, int(h * 0.12)), "おはようございます", font=font_greeting, fill=primary)
        
        # Date - clean format
        date_str = now.strftime("%Y年%m月%d日 %A")
        draw.text((left_x, int(h * 0.24)), date_str, font=font_date, fill=primary + (180,))

        # Subtle divider
        draw.line([(left_x, int(h * 0.30)), (w - left_x, int(h * 0.30))], fill=secondary + (80,), width=1)

        # Weather section
        if weather:
            draw.text((left_x, int(h * 0.35)), f"{weather['temp']}°C", font=font_weather_temp, fill=primary)
            draw.text((left_x + int(w * 0.15), int(h * 0.38)), weather['description'], font=font_weather_desc, fill=primary + (180,))
            draw.text((left_x + int(w * 0.15), int(h * 0.43)), f"湿度 {weather['humidity']}%", font=font_small, fill=primary + (150,))

        # Calendar events
        if events:
            event_y = int(h * 0.55)
            draw.text((left_x, event_y - int(h * 0.04)), "今日の予定", font=font_small, fill=accent)
            
            for event in events[:3]:
                time_str = event['time']
                title = event['title']
                draw.text((left_x, event_y), time_str, font=font_small, fill=primary + (150,))
                draw.text((left_x + int(w * 0.1), event_y), title, font=font_event, fill=primary)
                event_y += int(h * 0.06)

        # Footer - Season context
        footer_y = int(h * 0.85)
        draw.line([(left_x, footer_y), (w - left_x, footer_y)], fill=secondary + (60,), width=1)
        
        # Micro-season with context
        if season_info:
            season_label = f"時候: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            draw.text((left_x, footer_y + int(h * 0.03)), season_label, font=font_small, fill=accent)
            draw.text((w - left_x, footer_y + int(h * 0.03)), season_meaning, font=font_small, fill=primary + (120,), anchor="rt")

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
                "icon": data["weather"][0]["icon"],
                "humidity": data["main"]["humidity"],
            }
        except Exception as e:
            logger.warning(f"Failed to fetch weather for morning briefing: {e}")
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
                    "all_day": not isinstance(dtstart, datetime),
                })

            parsed.sort(key=lambda e: (e["all_day"], e["time"]))
            return parsed[:8]

        except Exception as e:
            logger.warning(f"Failed to fetch calendar for morning briefing: {e}")
            return []
