import logging
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_kansai_location_image
from utils.kansai_news import get_kansai_events_list
from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class KansaiEvents(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")
        
        season_info = get_full_season_info(now)
        palette = get_seasonal_palette(now)

        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        events = get_kansai_events_list(now, count=3)

        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            days_until_saturday = 0
        weekend_start = now.date() + timedelta(days=days_until_saturday)
        weekend_date = f"{weekend_start.strftime('%m月%d日')} Weekend"

        event_images = []
        for event in events:
            wiki_term = event.get("wiki", "")
            if not wiki_term and event.get("location"):
                wiki_term = event["location"]
            
            img = get_kansai_location_image(wiki_term, (200, 150)) if wiki_term else None
            if not img:
                img = self._generate_location_placeholder(event.get("wiki", "関西"), event.get("type", "イベント"), (200, 150))
            event_images.append(img)
        
        event_image_urls = []
        for i, img in enumerate(event_images):
            if img:
                import os
                static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'images', 'cache')
                os.makedirs(static_dir, exist_ok=True)
                image_path = os.path.join(static_dir, f'kansai_event_{i}.png')
                img.save(image_path, 'PNG')
                event_image_urls.append(f'/static/images/cache/kansai_event_{i}.png')
            else:
                event_image_urls.append(None)

        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]
            
            template_params = {
                "palette": palette,
                "season_info": season_info,
                "events": events,
                "event_images": event_image_urls,
                "weekend_date": weekend_date,
                "season_label": f"{season_info['micro_season']['kanji']} - {season_info['micro_season']['english']}" if season_info else "",
            }
            
            image = self.render_image(dimensions_for_render, "kansai_events.html", "kansai_events.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, events, season_info, palette, settings, now, weekend_date, event_images)

    def _draw_card_pil(self, dimensions, orientation, events, season_info, palette, settings, now, weekend_date, event_images):
        """Editorial-style events card with 55/45 split."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        img = Image.new('RGB', (w, h), '#FAF8F5')
        draw = ImageDraw.Draw(img)

        px = int(w * 0.045)
        py = int(h * 0.06)
        list_w = int(w * 0.52)
        img_x = list_w + int(w * 0.02)
        img_w = w - img_x - px
        img_h = h - py * 2

        f_weekend = get_font("Noto Sans JP", int(w * 0.016))
        f_header = get_font("Noto Serif JP", int(w * 0.03))
        f_tag = get_font("Noto Sans JP", int(w * 0.014))
        f_name = get_font("Noto Serif JP", int(w * 0.022))
        f_desc = get_font("Noto Sans JP", int(w * 0.016))
        f_loc = get_font("Noto Sans JP", int(w * 0.014))
        f_ms = get_font("Noto Serif JP", int(w * 0.014))
        f_ms_en = get_font("Noto Sans JP", int(w * 0.011))

        # Right side image
        if event_images and event_images[0]:
            img.paste(event_images[0].resize((img_w, img_h), Image.Resampling.LANCZOS), (img_x, py))
            draw = ImageDraw.Draw(img)
            draw.line([(img_x - 1, py), (img_x - 1, py + img_h)], fill='#E0D8C8', width=1)

        # Header
        draw.text((px, py), weekend_date, font=f_weekend, fill='#888888')
        draw.text((px, py + int(h * 0.04)), "週末のイベント", font=f_header, fill='#2C2C2C')

        # Event list
        ev_y = py + int(h * 0.12)
        ev_h = int(h * 0.26)
        for i, event in enumerate(events[:3]):
            y = ev_y + i * (ev_h + int(h * 0.015))
            
            # Tag with border
            tag = event.get('type', 'イベント')
            bbox = draw.textbbox((0, 0), tag, font=f_tag)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.rectangle([px, y, px + tw + 12, y + th + 6], outline='#B87333', width=1)
            draw.text((px + 6, y + 2), tag, font=f_tag, fill='#B87333')
            
            # Event name
            name_y = y + int(ev_h * 0.18)
            name = event.get("name", "")
            # Truncate if too long
            if len(name) > 45:
                name = name[:44] + "…"
            draw.text((px, name_y), name, font=f_name, fill='#2C2C2C')
            
            # Description (subtitle)
            desc = event.get("desc", "")
            if len(desc) > 60:
                desc = desc[:59] + "…"
            draw.text((px, name_y + int(ev_h * 0.3)), desc, font=f_desc, fill='#555555')
            
            # Location
            loc = event.get("location", "")
            if loc:
                draw.text((px, name_y + int(ev_h * 0.55)), f"場所: {loc}", font=f_loc, fill='#888888')
            
            # Divider
            if i < 2:
                div_y = y + ev_h + int(h * 0.005)
                draw.line([(px, div_y), (list_w - int(w * 0.02), div_y)], fill='#E0D8C8', width=1)

        # Micro-season
        if season_info:
            ms_x = list_w - int(w * 0.02)
            ms_y = h - int(h * 0.05)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill='#8B7355')
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.02)), e, font=f_ms_en, fill='#888888')

        return img

    def _generate_location_placeholder(self, location, event_type, size):
        """Generate a colored placeholder image with location name."""
        w, h = size
        img = Image.new('RGB', (w, h), '#E8E4DC')
        draw = ImageDraw.Draw(img)
        
        for y in range(h):
            c = int(232 * (1 - y / h * 0.1))
            draw.line([(0, y), (w, y)], fill=(c, c - 6, c - 14))
        
        f_loc = get_font("Noto Serif JP", int(w * 0.18))
        f_type = get_font("Noto Sans JP", int(w * 0.12))
        
        loc_text = location if location else "関西"
        bbox = draw.textbbox((0, 0), loc_text, font=f_loc)
        x = (w - (bbox[2]-bbox[0])) // 2
        y = (h - (bbox[3]-bbox[1])) // 2 - int(h * 0.1)
        draw.text((x, y), loc_text, font=f_loc, fill='#8B7355')
        
        bbox2 = draw.textbbox((0, 0), event_type, font=f_type)
        draw.text(((w - (bbox2[2]-bbox2[0])) // 2, y + (bbox[3]-bbox[1]) + int(h * 0.05)), event_type, font=f_type, fill='#AAAAAA')
        
        return img
