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
        
        image_data_uri = self.image_to_data_uri(morning_image)

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
                "morning_image": image_data_uri,
                "image_label": season_info['micro_season']['kanji'] if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "morning_briefing.html", "morning_briefing.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, now, season_info, palette, 
                                   weather_data, calendar_events, time_format, morning_image)

    def _draw_card_pil(self, dimensions, orientation, now, season_info, palette, 
                       weather, events, time_format, morning_image):
        """Elegant planner-style morning briefing."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        img = Image.new('RGB', (w, h), '#FAF8F5')
        draw = ImageDraw.Draw(img)

        px = int(w * 0.05)
        py = int(h * 0.07)
        right_col_x = int(w * 0.58)
        col_gap = int(w * 0.04)
        left_max = right_col_x - col_gap

        f_greeting = get_font("Noto Serif JP", int(w * 0.055))
        f_date = get_font("Noto Sans JP", int(w * 0.02))
        f_temp = get_font("Noto Serif JP", int(w * 0.06))
        f_msg = get_font("Noto Sans JP", int(w * 0.02))
        f_sched_h = get_font("Noto Serif JP", int(w * 0.025))
        f_sched_t = get_font("Noto Sans JP", int(w * 0.017))
        f_sched_e = get_font("Noto Serif JP", int(w * 0.02))
        f_ms = get_font("Noto Serif JP", int(w * 0.016))
        f_ms_en = get_font("Noto Sans JP", int(w * 0.012))

        # Right column image
        if morning_image:
            ix, iy = right_col_x, py
            iw = w - right_col_x - px
            ih = h - py * 2
            img.paste(morning_image.resize((iw, ih), Image.Resampling.LANCZOS), (ix, iy))
            draw = ImageDraw.Draw(img)
            draw.rectangle([ix-2, iy-2, ix+iw+2, iy+ih+2], outline='#E0D8C8', width=1)

        # Date line
        draw.text((px, py), now.strftime('%m月%d日') + ' • 姫路市', font=f_date, fill='#888888')

        # Greeting
        gy = py + int(h * 0.055)
        draw.text((px, gy), "おはようございます。", font=f_greeting, fill='#2C2C2C')

        # Divider
        dy = gy + int(h * 0.075)
        draw.line([(px, dy), (left_max, dy)], fill='#E0D8C8', width=1)

        # Weather message
        my = dy + int(h * 0.04)
        if weather:
            lines = [f"今日は{weather['description']}です。", f"湿度 {weather['humidity']}% です。"]
        else:
            lines = ["今日は一日を通して穏やかな晴天です。", "朝晩は冷え込むので羽織るものを。"]
        for i, line in enumerate(lines):
            draw.text((px, my + i * int(h * 0.032)), line, font=f_msg, fill='#555555')

        # Temperature
        ty = my + int(h * 0.1)
        temp_str = f"{weather['temp']}°" if weather else "21°"
        draw.text((px, ty), temp_str, font=f_temp, fill='#7A8B6F')
        draw.text((px + int(w * 0.11), ty + int(h * 0.018)), "現在気温", font=f_date, fill='#888888')

        # Schedule (right column)
        sx = right_col_x + int(w * 0.02)
        sy = py
        draw.text((sx, sy), "今日の予定", font=f_sched_h, fill='#8B7355')
        
        item_y = sy + int(h * 0.055)
        if events:
            for ev in events[:4]:
                draw.text((sx, item_y), ev['time'], font=f_sched_t, fill='#888888')
                draw.text((sx, item_y + int(h * 0.004)), ev['title'], font=f_sched_e, fill='#2C2C2C')
                # Dotted underline
                bbox = draw.textbbox((sx, item_y + int(h * 0.004)), ev['title'], font=f_sched_e)
                tw = bbox[2] - bbox[0]
                for dx in range(0, tw, 4):
                    draw.line([(sx + dx, item_y + int(h * 0.03)), (sx + dx + 2, item_y + int(h * 0.03))], fill='#E0D8C8', width=1)
                item_y += int(h * 0.05)
        else:
            draw.text((sx, item_y), "本日の予定はありません", font=f_sched_t, fill='#888888')

        # Micro-season stamp
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
