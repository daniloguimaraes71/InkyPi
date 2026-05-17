import logging
import requests
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info

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
        tomorrow_weather = self._get_tomorrow_weather(device_config, tz, now)
        tomorrow_events = self._get_tomorrow_events(settings, device_config, tz, now)

        template_params = {
            "now": now,
            "time_format": time_format,
            "season_info": season_info,
            "weather": tomorrow_weather,
            "events": tomorrow_events,
            "plugin_settings": settings,
        }

        image = self.render_image(dimensions, "evening_card.html", "evening_card.css", template_params)
        if not image:
            raise RuntimeError("Failed to render evening card.")
        return image

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
