"""
Wpotd Plugin for InkyPi
This plugin fetches the Wikipedia Picture of the Day (Wpotd) from Wikipedia's API
and displays it on the InkyPi device with a blurred background, title, and description.

Wikipedia API Documentation: https://www.mediawiki.org/wiki/API:Main_page
Picture of the Day example: https://www.mediawiki.org/wiki/API:Picture_of_the_day_viewer
Github Repository: https://github.com/wikimedia/mediawiki-api-demos/tree/master/apps/picture-of-the-day-viewer
Wikimedia requires a User Agent header for API requests, which is set in the SESSION headers:
https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy

Flow:

1. Fetch the date to use for the Picture of the Day (POTD) based on settings. (_determine_date)
2. Make an API request to fetch the POTD data for that date. (_fetch_potd)
3. Extract the image filename from the response. (_fetch_potd)
4. Make another API request to get the image URL. (_fetch_image_src)
5. Download the original image from the URL. (_download_image)
6. Apply blurred background with centered image (no upscaling). (pad_image_blur)
7. Overlay title and description at the bottom. (painting-of-the-day style layout)
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageDraw, UnidentifiedImageError
from io import BytesIO
from utils.http_client import get_http_session
from utils.image_utils import pad_image_blur
from utils.app_utils import get_font
from utils.design_variants import get_variant
import logging
from random import randint
from datetime import datetime, timedelta, date
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Wpotd(BasePlugin):
    HEADERS = {'User-Agent': 'InkyPi/1.0 (https://github.com/fatihak/InkyPi/)'}
    API_URL = "https://en.wikipedia.org/w/api.php"

    def generate_settings_template(self) -> Dict[str, Any]:
        template_params = super().generate_settings_template()
        template_params['style_settings'] = False
        return template_params

    def generate_image(self, settings: Dict[str, Any], device_config: Dict[str, Any]) -> Image.Image:
        logger.info("=== Wikipedia POTD Plugin: Starting image generation ===")

        datetofetch = self._determine_date(settings)
        logger.info(f"Fetching Wikipedia Picture of the Day for: {datetofetch}")

        data = self._fetch_potd(datetofetch)
        picurl = data["image_src"]
        title = data.get("title", "Picture of the Day")
        description = data.get("description", "")
        logger.info(f"Image URL: {picurl}")

        # Get dimensions
        max_width, max_height = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            max_width, max_height = max_height, max_width

        dimensions = (max_width, max_height)

        # Download original image (no resize — pad_image_blur handles fitting)
        image = self._download_image(picurl, dimensions=dimensions, resize=False)
        if image is None:
            logger.error("Failed to download WPOTD image")
            raise RuntimeError("Failed to download WPOTD image.")

        # Apply blurred background with centered image (painting-of-the-day style)
        img = pad_image_blur(image.convert("RGB"), dimensions)

        v = get_variant(device_config.get_config("design_style"), None)

        # Overlay title and description
        overlay_height = int(max_height * 0.22)
        overlay_y = max_height - overlay_height
        overlay = Image.new("RGBA", (max_width, overlay_height), (0, 0, 0, 140))
        img.paste(Image.alpha_composite(
            Image.new("RGBA", (max_width, overlay_height), (0, 0, 0, 0)),
            overlay
        ), (0, overlay_y))

        draw = ImageDraw.Draw(img)

        primary = (255, 255, 255)
        secondary = (200, 200, 200)

        font_title = get_font(v.heading_font, int(max_width * 0.035))
        font_desc = get_font(v.body_font, int(max_width * 0.025))

        text_x = int(max_width * 0.05)
        text_y = overlay_y + int(overlay_height * 0.15)

        draw.text((text_x, text_y), title, font=font_title, fill=primary)

        if description:
            wrapped = self._wrap_text(description, font_desc, int(max_width * 0.9))
            line_y = text_y + int(max_width * 0.04)
            for line in wrapped[:3]:
                draw.text((text_x, line_y), line, font=font_desc, fill=secondary)
                line_y += int(max_width * 0.028)

        # Attribution
        draw.text((text_x, text_y + int(max_width * 0.10)),
                  "Wikipedia Picture of the Day", font=font_desc, fill=secondary + (180,))

        logger.info("=== Wikipedia POTD Plugin: Image generation complete ===")
        return img

    def _determine_date(self, settings: Dict[str, Any]) -> date:
        if settings.get("randomizeWpotd") == "true":
            start = datetime(2015, 1, 1)
            delta_days = (datetime.today() - start).days
            return (start + timedelta(days=randint(0, delta_days))).date()
        elif settings.get("customDate"):
            return datetime.strptime(settings["customDate"], "%Y-%m-%d").date()
        else:
            return datetime.today().date()

    def _download_image(self, url: str, dimensions: tuple = None, resize: bool = False) -> Image.Image:
        """
        Download image from URL, optionally resizing with adaptive loader.

        Args:
            url: Image URL
            dimensions: Target dimensions if resizing
            resize: Whether to use adaptive resizing
        """
        try:
            if url.lower().endswith(".svg"):
                logger.warning("SVG format is not supported by Pillow. Skipping image download.")
                raise RuntimeError("Unsupported image format: SVG.")

            if resize and dimensions:
                # Use adaptive loader for memory-efficient processing
                return self.image_loader.from_url(url, dimensions, timeout_ms=10000, headers=self.HEADERS)
            else:
                # Original behavior: download without resizing
                session = get_http_session()
                response = session.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))

        except UnidentifiedImageError as e:
            logger.error(f"Unsupported image format at {url}: {str(e)}")
            raise RuntimeError("Unsupported image format.")
        except Exception as e:
            logger.error(f"Failed to load WPOTD image from {url}: {str(e)}")
            raise RuntimeError("Failed to load WPOTD image.")

    def _fetch_potd(self, cur_date: date) -> Dict[str, Any]:
        potd_title = f"Template:POTD/{cur_date.isoformat()}"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "images",
            "titles": potd_title
        }

        data = self._make_request(params)
        try:
            filename = data["query"]["pages"][0]["images"][0]["title"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to retrieve POTD filename for {cur_date}: {e}")
            raise RuntimeError("Failed to retrieve POTD filename.")

        image_src = self._fetch_image_src(filename)
        description = self._fetch_description(potd_title)

        # Build title from filename, removing File: prefix and underscores
        display_title = filename.replace("File:", "").replace("_", " ").strip()

        return {
            "filename": filename,
            "image_src": image_src,
            "image_page_url": f"https://en.wikipedia.org/wiki/{potd_title}",
            "date": cur_date,
            "title": display_title,
            "description": description
        }

    def _fetch_description(self, page_title: str) -> str:
        """Fetch the plain-text extract/description for a Wikipedia page."""
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "extracts",
            "titles": page_title,
            "exintro": "1",
            "explaintext": "1",
            "exchars": "400",
        }
        try:
            data = self._make_request(params)
            pages = data.get("query", {}).get("pages", [])
            if pages:
                extract = pages[0].get("extract", "")
                if extract:
                    return extract.strip()
        except Exception as e:
            logger.warning(f"Failed to fetch description for {page_title}: {e}")
        return ""

    @staticmethod
    def _wrap_text(text, font, max_width):
        """Wrap text to fit within max_width pixels."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = font.getbbox(test)
            if bbox and (bbox[2] - bbox[0]) > max_width:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        return lines if lines else [text]

    def _fetch_image_src(self, filename: str) -> str:
        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url",
            "titles": filename
        }
        data = self._make_request(params)
        try:
            page = next(iter(data["query"]["pages"].values()))
            return page["imageinfo"][0]["url"]
        except (KeyError, IndexError, StopIteration) as e:
            logger.error(f"Failed to retrieve image URL for {filename}: {e}")
            raise RuntimeError("Failed to retrieve image URL.")

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            session = get_http_session()
            response = session.get(self.API_URL, params=params, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Wikipedia API request failed with params {params}: {str(e)}")
            raise RuntimeError("Wikipedia API request failed.")
