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

        # Determine current season
        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        # Get 2-3 events from live news or backup
        events = get_kansai_events_list(now, count=3)

        # Find next weekend
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() == 5:
            days_until_saturday = 0
        weekend_start = now.date() + timedelta(days=days_until_saturday)
        weekend_date = f"{weekend_start.strftime('%m月%d日')} Weekend"

        # Get images for each event
        event_images = []
        for event in events:
            wiki_term = event.get("wiki", "")
            if not wiki_term and event.get("location"):
                wiki_term = event["location"]
            
            img = get_kansai_location_image(wiki_term, (200, 150)) if wiki_term else None
            
            # If no Wikipedia image, generate a location-based placeholder
            if not img:
                img = self._generate_location_placeholder(event.get("wiki", "関西"), event.get("type", "イベント"), (200, 150))
            
            event_images.append(img)
        
        # Save images to static cache for HTML rendering
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

        # Try HTML render first, fall back to PIL
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

        # Fallback to PIL rendering
        return self._draw_card_pil(dimensions, orientation, events, season_info, palette, settings, now, weekend_date, event_images)

    def _draw_card_pil(self, dimensions, orientation, events, season_info, palette, settings, now, weekend_date, event_images):
        """Fallback PIL rendering with multiple events."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        # Create base image
        bg_color = '#FAF8F5'
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)

        # Fonts
        font_title = get_font("Noto Serif JP", int(w * 0.04))
        font_desc = get_font("Noto Sans JP", int(w * 0.028))
        font_info = get_font("Noto Sans JP", int(w * 0.025))
        font_label = get_font("Noto Sans JP", int(w * 0.022))
        font_header = get_font("Noto Serif JP", int(w * 0.035))

        # Header
        draw.text((int(w * 0.05), int(h * 0.03)), weekend_date, font=font_label, fill='#999999')
        draw.text((int(w * 0.05), int(h * 0.08)), "週末のイベント", font=font_header, fill='#2C2C2C')

        # Display events in a list format
        y_start = int(h * 0.16)
        event_height = int(h * 0.26)
        
        for i, (event, event_img) in enumerate(zip(events, event_images)):
            y = y_start + i * (event_height + int(h * 0.02))
            
            # Event image thumbnail
            if event_img:
                thumb_x, thumb_y = int(w * 0.05), y
                thumb_w, thumb_h = int(w * 0.15), int(event_height * 0.8)
                thumb = event_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                img.paste(thumb, (thumb_x, thumb_y))
                
                # Border
                draw.rectangle([thumb_x-1, thumb_y-1, thumb_x+thumb_w+1, thumb_y+thumb_h+1], 
                              outline='#E0D8C8', width=1)
                
                text_x = thumb_x + thumb_w + int(w * 0.03)
            else:
                text_x = int(w * 0.05)
            
            # Event type tag
            draw.text((text_x, y), f"{event.get('type', 'イベント')}", font=font_label, fill='#8B7355')
            
            # Event title
            draw.text((text_x, y + int(event_height * 0.18)), event.get("name", ""), font=font_title, fill='#2C2C2C')
            
            # Description
            draw.text((text_x, y + int(event_height * 0.52)), event.get("desc", ""), font=font_desc, fill='#666666')
            
            # Location
            if event.get("location"):
                draw.text((text_x, y + int(event_height * 0.78)), f"場所: {event['location']}", font=font_info, fill='#999999')

        return img

    def _generate_location_placeholder(self, location, event_type, size):
        """Generate a colored placeholder image with location name."""
        w, h = size
        img = Image.new('RGB', (w, h), '#E8E4DC')
        draw = ImageDraw.Draw(img)
        
        # Add a subtle gradient effect
        for y in range(h):
            alpha = int(255 * (1 - y / h * 0.15))
            draw.line([(0, y), (w, y)], fill=(alpha, alpha - 8, alpha - 16))
        
        # Location name in center
        font_loc = get_font("Noto Serif JP", int(w * 0.18))
        font_type = get_font("Noto Sans JP", int(w * 0.12))
        
        # Draw location
        loc_text = location if location else "関西"
        bbox = draw.textbbox((0, 0), loc_text, font=font_loc)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (w - text_w) // 2
        y = (h - text_h) // 2 - int(h * 0.1)
        draw.text((x, y), loc_text, font=font_loc, fill='#8B7355')
        
        # Draw event type below
        bbox2 = draw.textbbox((0, 0), event_type, font=font_type)
        tw2 = bbox2[2] - bbox2[0]
        x2 = (w - tw2) // 2
        y2 = y + text_h + int(h * 0.05)
        draw.text((x2, y2), event_type, font=font_type, fill='#AAAAAA')
        
        return img
