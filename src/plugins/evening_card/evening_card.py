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

        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"
        
        # Fetch image based on tomorrow's weather or fallback to seasonal
        if tomorrow_weather:
            desc = tomorrow_weather.get("description", "").lower()
            if "rain" in desc or "雨" in desc:
                image_keyword = "Rain"
            elif "cloud" in desc or "曇" in desc:
                image_keyword = "Cloud"
            elif "snow" in desc or "雪" in desc:
                image_keyword = "Snow"
            elif "clear" in desc or "晴" in desc:
                image_keyword = "Sunset"
            else:
                image_keyword = EVENING_IMAGES.get(season, "Sunset")
        else:
            image_keyword = EVENING_IMAGES.get(season, "Sunset")
        
        evening_image = get_wikipedia_image(image_keyword, (320, 240))
        
        image_data_uri = self.image_to_data_uri(evening_image)

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
                "evening_image": image_data_uri,
                "image_label": season_info['micro_season']['kanji'] if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "evening_card.html", "evening_card.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, 
                                   tomorrow_weather, tomorrow_events, time_format, evening_image)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, 
                       weather, events, time_format, evening_image):
        """Elegant evening reflection card."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        img = Image.new('RGB', (w, h), '#F5F7FA')
        draw = ImageDraw.Draw(img)

        px = int(w * 0.05)
        py = int(h * 0.07)

        f_greeting = get_font("Noto Serif JP", int(w * 0.04))
        f_sub = get_font("Noto Sans JP", int(w * 0.02))
        f_label = get_font("Noto Sans JP", int(w * 0.016))
        f_weather = get_font("Noto Serif JP", int(w * 0.032))
        f_sched_h = get_font("Noto Serif JP", int(w * 0.022))
        f_sched_t = get_font("Noto Sans JP", int(w * 0.016))
        f_sched_e = get_font("Noto Serif JP", int(w * 0.018))
        f_ms = get_font("Noto Serif JP", int(w * 0.016))
        f_ms_en = get_font("Noto Sans JP", int(w * 0.012))

        # Greeting
        draw.text((px, py), "今日も一日、お疲れ様でした。", font=f_greeting, fill='#2C2C2C')
        draw.text((px, py + int(h * 0.06)), "ゆっくりとお茶を淹れて、一息つきましょう。", font=f_sub, fill='#555555')

        # Divider
        dy = py + int(h * 0.14)
        draw.line([(px, dy), (w - px, dy)], fill='#E0D8C8', width=1)

        # Tomorrow's weather
        ty = dy + int(h * 0.05)
        draw.text((px, ty), "明日の天気", font=f_label, fill='#8B7355')
        if weather:
            draw.text((px, ty + int(h * 0.04)), weather['description'], font=f_weather, fill='#2C2C2C')
            note = f"最高{weather['high']}°C / 最低{weather['low']}°C"
            if '雨' in weather['description']:
                note += " • 傘をお持ちください"
            draw.text((px, ty + int(h * 0.09)), note, font=f_sub, fill='#555555')
        else:
            draw.text((px, ty + int(h * 0.04)), "晴れのち曇り", font=f_weather, fill='#2C2C2C')
            draw.text((px, ty + int(h * 0.09)), "明日も良い一日になりますように。", font=f_sub, fill='#555555')

        # Tomorrow's schedule
        if events:
            sy = ty + int(h * 0.18)
            draw.line([(px, sy), (w - px, sy)], fill='#E0D8C8', width=1)
            sy += int(h * 0.04)
            draw.text((px, sy), "明日の予定", font=f_label, fill='#8B7355')
            item_y = sy + int(h * 0.045)
            for ev in events[:3]:
                draw.text((px, item_y), ev['time'], font=f_sched_t, fill='#888888')
                draw.text((px + int(w * 0.09), item_y), ev['title'], font=f_sched_e, fill='#2C2C2C')
                bbox = draw.textbbox((px + int(w * 0.09), item_y), ev['title'], font=f_sched_e)
                tw = bbox[2] - bbox[0]
                for dx in range(0, tw, 4):
                    draw.line([(px + int(w * 0.09) + dx, item_y + int(h * 0.028)), (px + int(w * 0.09) + dx + 2, item_y + int(h * 0.028))], fill='#E0D8C8', width=1)
                item_y += int(h * 0.05)

        # Small image top-right
        if evening_image:
            ix = w - px - int(w * 0.22)
            iy = py
            iw = int(w * 0.22)
            ih = int(h * 0.22)
            img.paste(evening_image.resize((iw, ih), Image.Resampling.LANCZOS), (ix, iy))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ix-2, iy-2, ix+iw+2, iy+ih+2], outline='#E0D8C8', width=1)

        # Micro-season
        if season_info:
            ms_x = w - px
            ms_y = h - int(h * 0.055)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill='#8B7355')
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.022)), e, font=f_ms_en, fill='#888888')

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
