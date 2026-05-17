import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info

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
        weather_data = self._get_weather_summary(device_config, tz)
        calendar_events = self._get_calendar_events(settings, device_config, tz, now)

        greeting = self._get_greeting(now.hour)

        template_params = {
            "now": now,
            "time_format": time_format,
            "greeting": greeting,
            "season_info": season_info,
            "weather": weather_data,
            "events": calendar_events,
            "plugin_settings": settings,
        }

        image = self.render_image(dimensions, "morning_briefing.html", "morning_briefing.css", template_params)
        if not image:
            raise RuntimeError("Failed to render morning briefing card.")
        return image

    def _get_greeting(self, hour):
        if hour < 10:
            return "おはようございます"
        elif hour < 12:
            return "おはようございます"
        else:
            return "おはようございます"

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
