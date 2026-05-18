import logging
import random
import requests
import pytz
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info
from utils.image_utils import pad_image_blur
from utils.design_variants import get_variant

logger = logging.getLogger(__name__)

GLOBAL_ART_KEYWORDS = {
    "spring": [
        "cherry blossom", "plum blossom", "spring landscape",
        "spring festival", "holi", "basant",
        "persian garden", "spring garden",
        "spring flowers", "pastoral spring",
        "spring landscape", "flowers",
        "african landscape", "savanna",
    ],
    "summer": [
        "summer landscape", "lotus", "bamboo",
        "monsoon", "tropical garden",
        "desert oasis", "caravan",
        "summer harvest", "seaside",
        "tropical landscape", "summer beach",
        "african summer", "market scene",
    ],
    "autumn": [
        "autumn maple", "harvest moon", "chrysanthemum",
        "autumn festival", "diwali",
        "autumn garden", "vineyard",
        "autumn harvest", "wine harvest",
        "autumn forest", "fall colors",
        "african autumn", "harvest scene",
    ],
    "winter": [
        "winter snow", "pine and snow", "winter plum",
        "winter mountain", "himalaya",
        "winter desert", "snow mountain",
        "winter landscape", "snow scene",
        "winter forest", "snowy mountain",
        "winter savanna", "mountain landscape",
    ],
}

CURATED_THEMES = [
    "japanese art", "ukiyo-e", "woodblock print",
    "chinese painting", "chinese landscape", "ink wash",
    "korean art", "korean landscape",
    "indian miniature", "mughal painting", "rajput painting",
    "persian miniature", "persian art",
    "thai art", "balinese art", "indonesian art",
    "african art", "ethiopian art", "nigerian art",
    "mexican art", "peruvian art", "aztec art", "inca art",
    "islamic art", "arabic calligraphy",
    "impressionism", "post-impressionism", "art nouveau",
    "contemporary art", "modern art",
]

MET_API = "https://collectionapi.metmuseum.org/public/collection/v1"


class Painting(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        v = get_variant(settings.get("designStyle"))
        season_info = get_full_season_info(now)
        source = settings.get("artSource", "met")

        painting = self._fetch_painting(source, season_info, settings, now)
        if not painting:
            raise RuntimeError("Failed to fetch painting. Please try again.")

        return self._render_painting_card(dimensions, painting, season_info, settings, v)

    def _fetch_painting(self, source, season_info, settings, now):
        if source == "met":
            return self._fetch_from_met(season_info, settings, now)
        return self._fetch_from_met(season_info, settings, now)

    def _fetch_from_met(self, season_info, settings, now):
        try:
            month = now.month
            if month in [3, 4, 5]:
                season = "spring"
            elif month in [6, 7, 8]:
                season = "summer"
            elif month in [9, 10, 11]:
                season = "autumn"
            else:
                season = "winter"

            seed = now.year * 10000 + now.month * 100 + now.day
            random.seed(seed)

            candidates = []
            if random.random() < 0.5:
                candidates = list(CURATED_THEMES)
            else:
                candidates = list(GLOBAL_ART_KEYWORDS.get(season, ["landscape"]))

            random.shuffle(candidates)
            random.seed()

            if settings.get("searchKeyword"):
                candidates = [settings["searchKeyword"]] + candidates

            for keyword in candidates:
                logger.info(f"Searching Met for: {keyword}")

                search_url = f"{MET_API}/search?q={keyword}&hasImages=true"
                resp = requests.get(search_url, timeout=15)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                object_ids = data.get("objectIDs")
                if not object_ids:
                    continue

                random.shuffle(object_ids)
                for obj_id in object_ids[:8]:
                    obj_url = f"{MET_API}/objects/{obj_id}"
                    obj_resp = requests.get(obj_url, timeout=10)
                    if obj_resp.status_code != 200:
                        continue

                    obj = obj_resp.json()
                    primary_image = obj.get("primaryImage")
                    if primary_image:
                        culture = obj.get("culture", "")
                        period = obj.get("period", "")
                        dynasty = obj.get("dynasty", "")

                        artist = obj.get("artistDisplayName", "Unknown")
                        if culture:
                            artist = f"{artist} ({culture})" if artist != "Unknown" else culture

                        return {
                            "title": obj.get("title", "Untitled"),
                            "artist": artist,
                            "date": obj.get("objectDate", ""),
                            "image_url": primary_image,
                            "source": "Metropolitan Museum of Art",
                            "culture": culture,
                            "period": period,
                        }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch from Met: {e}")
            return None

    def _render_painting_card(self, dimensions, painting, season_info, settings, v):
        w, h = dimensions
        C = v.colors

        try:
            img = self.image_loader.from_url(painting["image_url"], dimensions, resize=False, timeout_ms=30000)
        except Exception as e:
            logger.warning(f"Failed to load image with adaptive loader: {e}")
            try:
                from utils.http_client import get_http_session
                from io import BytesIO
                session = get_http_session()
                headers = {'User-Agent': 'InkyPi/1.0'}
                resp = session.get(painting["image_url"], headers=headers, timeout=20)
                if resp.status_code == 200:
                    from PIL import Image
                    img = Image.open(BytesIO(resp.content))
                else:
                    img = None
            except Exception as e2:
                logger.error(f"Fallback download also failed: {e2}")
                img = None

        if not img:
            raise RuntimeError("Failed to load painting image.")

        img = pad_image_blur(img.convert("RGB"), dimensions)

        from PIL import Image, ImageDraw, ImageFont
        from utils.app_utils import get_font

        draw = ImageDraw.Draw(img)

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

        font_title = get_font(v.heading_font, int(w * 0.035))
        font_info = get_font(v.body_font, int(w * 0.025))

        text_x = int(w * 0.05)
        text_y = overlay_y + int(overlay_height * 0.15)

        draw.text((text_x, text_y), painting["title"], font=font_title, fill=primary)

        info = painting["artist"]
        if painting.get("date"):
            info += f" · {painting['date']}"
        draw.text((text_x, text_y + int(w * 0.04)), info, font=font_info, fill=secondary)

        draw.text((text_x, text_y + int(w * 0.07)), painting["source"], font=font_info, fill=secondary + (180,))

        if season_info:
            season_label = season_info["micro_season"]["kanji"]
            font_season = get_font(v.heading_font, int(w * 0.025))
            draw.text((w - int(w * 0.03), int(h * 0.03)), season_label,
                      font=font_season, fill=(255, 255, 255, 180), anchor="rt")

        return img
