import logging
import random
import requests
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info
from utils.image_utils import pad_image_blur

logger = logging.getLogger(__name__)

# Curated list of seasonal painting themes
SEASONAL_KEYWORDS = {
    "spring": ["cherry blossom", "flower", "garden", "landscape"],
    "summer": ["beach", "sea", "summer", "garden", "landscape"],
    "autumn": ["autumn", "fall", "maple", "harvest", "landscape"],
    "winter": ["snow", "winter", "mountain", "landscape"],
}

MET_API = "https://collectionapi.metmuseum.org/public/collection/v1"


class Painting(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        season_info = get_full_season_info(now)
        source = settings.get("artSource", "met")

        painting = self._fetch_painting(source, season_info, settings)
        if not painting:
            raise RuntimeError("Failed to fetch painting. Please try again.")

        return self._render_painting_card(dimensions, painting, season_info, settings)

    def _fetch_painting(self, source, season_info, settings):
        if source == "met":
            return self._fetch_from_met(season_info, settings)
        return self._fetch_from_met(season_info, settings)

    def _fetch_from_met(self, season_info, settings):
        try:
            # Determine seasonal search query
            month = datetime.now().month
            if month in [3, 4, 5]:
                season = "spring"
            elif month in [6, 7, 8]:
                season = "summer"
            elif month in [9, 10, 11]:
                season = "autumn"
            else:
                season = "winter"

            keywords = SEASONAL_KEYWORDS.get(season, ["landscape"])
            keyword = settings.get("searchKeyword", random.choice(keywords))

            # Search for objects with images
            search_url = f"{MET_API}/search?q={keyword}&hasImages=true"
            resp = requests.get(search_url, timeout=15)
            if resp.status_code != 200:
                return None

            data = resp.json()
            object_ids = data.get("objectIDs", [])
            if not object_ids:
                return None

            # Try up to 5 random objects to find one with a valid image
            random.shuffle(object_ids)
            for obj_id in object_ids[:5]:
                obj_url = f"{MET_API}/objects/{obj_id}"
                obj_resp = requests.get(obj_url, timeout=10)
                if obj_resp.status_code != 200:
                    continue

                obj = obj_resp.json()
                primary_image = obj.get("primaryImage")
                if primary_image:
                    return {
                        "title": obj.get("title", "Untitled"),
                        "artist": obj.get("artistDisplayName", "Unknown"),
                        "date": obj.get("objectDate", ""),
                        "image_url": primary_image,
                        "source": "Metropolitan Museum of Art",
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch from Met: {e}")
            return None

    def _render_painting_card(self, dimensions, painting, season_info, settings):
        w, h = dimensions

        # Load and resize painting image
        img = self.image_loader.from_url(painting["image_url"], dimensions, resize=False)
        if not img:
            raise RuntimeError("Failed to load painting image.")

        # Fit image to screen with blur padding
        img = pad_image_blur(img.convert("RGB"), dimensions)

        # Add overlay with painting info
        from PIL import Image, ImageDraw, ImageFont
        from utils.app_utils import get_font

        draw = ImageDraw.Draw(img)

        # Semi-transparent overlay at bottom
        overlay_height = int(h * 0.22)
        overlay_y = h - overlay_height
        overlay = Image.new("RGBA", (w, overlay_height), (0, 0, 0, 140))
        img.paste(Image.alpha_composite(
            Image.new("RGBA", (w, overlay_height), (0, 0, 0, 0)),
            overlay
        ), (0, overlay_y))

        draw = ImageDraw.Draw(img)

        primary = (255, 255, 255)
        secondary = (200, 200, 200)

        font_title = get_font("Noto Serif JP", int(w * 0.035))
        font_info = get_font("Jost", int(w * 0.025))

        text_x = int(w * 0.05)
        text_y = overlay_y + int(overlay_height * 0.15)

        # Title
        draw.text((text_x, text_y), painting["title"], font=font_title, fill=primary)

        # Artist and date
        info = painting["artist"]
        if painting.get("date"):
            info += f" · {painting['date']}"
        draw.text((text_x, text_y + int(w * 0.04)), info, font=font_info, fill=secondary)

        # Source
        draw.text((text_x, text_y + int(w * 0.07)), painting["source"], font=font_info, fill=secondary + (180,))

        # Micro-season in corner
        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            font_season = get_font("Noto Serif JP", int(w * 0.025))
            draw.text((w - int(w * 0.03), int(h * 0.03)), season_label,
                      font=font_season, fill=(255, 255, 255, 180), anchor="rt")

        return img
