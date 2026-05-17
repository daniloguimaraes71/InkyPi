import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.card_design import CardDesign
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
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)
        weather_data = self._get_weather_summary(device_config, tz)
        calendar_events = self._get_calendar_events(settings, device_config, tz, now)

        return self._draw_card(dimensions, orientation, now, season_info, palette, 
                              weather_data, calendar_events, settings, time_format)

    def _draw_card(self, dimensions, orientation, now, season_info, palette, 
                   weather, events, settings, time_format):
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Initialize design system
        design = CardDesign((w, h), orientation)
        
        # Create base card
        img = design.create_base_card(palette=palette)
        draw = ImageDraw.Draw(img)

        # Header
        y_pos = design.draw_header(draw, "おはようございます", 
                                  now.strftime("%Y年%m月%d日 %A"))

        # Weather section
        if weather:
            y_pos = design.draw_section(draw, "天気", y_pos)
            
            # Temperature - large
            draw.text((design.margin, y_pos), f"{weather['temp']}°C", 
                     font=design.fonts['h1'], fill=design.COLORS['text_primary'])
            
            # Description
            draw.text((design.margin + int(w * 0.15), y_pos + int(h * 0.02)), 
                     weather['description'], font=design.fonts['body'], 
                     fill=design.COLORS['text_secondary'])
            
            # Humidity
            draw.text((design.margin + int(w * 0.15), y_pos + int(h * 0.06)), 
                     f"湿度 {weather['humidity']}%", font=design.fonts['caption'], 
                     fill=design.COLORS['text_light'])
            
            y_pos += int(h * 0.12)

        # Calendar events
        if events:
            y_pos = design.draw_section(draw, "今日の予定", y_pos)
            
            for event in events[:3]:
                # Time
                draw.text((design.margin, y_pos), event['time'], 
                         font=design.fonts['caption'], fill=design.COLORS['text_light'])
                
                # Title
                draw.text((design.margin + int(w * 0.1), y_pos), event['title'], 
                         font=design.fonts['body'], fill=design.COLORS['text_primary'])
                
                y_pos += int(h * 0.06)

        # Footer
        design.draw_footer(draw, now.strftime("%Y年%m月%d日"), season_info)

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
