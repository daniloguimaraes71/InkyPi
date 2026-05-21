from __future__ import annotations
import requests
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from io import BytesIO
import os
import logging
import hashlib
import tempfile
import subprocess
import shutil
import json
import time
import socket

logger = logging.getLogger(__name__)

def get_image(image_url):
    response = requests.get(image_url, timeout=30)
    img = None
    if 200 <= response.status_code < 300 or response.status_code == 304:
        img = Image.open(BytesIO(response.content))
    else:
        logger.error(f"Received non-200 response from {image_url}: status_code: {response.status_code}")
    return img

def change_orientation(image, orientation, inverted=False):
    if orientation == 'horizontal':
        angle = 0
    elif orientation == 'vertical':
        angle = 90

    if inverted:
        angle = (angle + 180) % 360

    return image.rotate(angle, expand=1)

def resize_image(image, desired_size, image_settings=[]):
    img_width, img_height = image.size
    desired_width, desired_height = desired_size
    desired_width, desired_height = int(desired_width), int(desired_height)

    img_ratio = img_width / img_height
    desired_ratio = desired_width / desired_height

    keep_width = "keep-width" in image_settings

    x_offset, y_offset = 0,0
    new_width, new_height = img_width,img_height
    # Step 1: Determine crop dimensions
    desired_ratio = desired_width / desired_height
    if img_ratio > desired_ratio:
        # Image is wider than desired aspect ratio
        new_width = int(img_height * desired_ratio)
        if not keep_width:
            x_offset = (img_width - new_width) // 2
    else:
        # Image is taller than desired aspect ratio
        new_height = int(img_width / desired_ratio)
        if not keep_width:
            y_offset = (img_height - new_height) // 2

    # Step 2: Crop the image
    image = image.crop((x_offset, y_offset, x_offset + new_width, y_offset + new_height))

    # Step 3: Resize to the exact desired dimensions (if necessary)
    return image.resize((desired_width, desired_height), Image.LANCZOS)

def apply_image_enhancement(img, image_settings={}):
    # Convert image to RGB mode if necessary for enhancement operations
    # ImageEnhance requires RGB mode for operations like blend
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
        

    # Apply Brightness
    img = ImageEnhance.Brightness(img).enhance(image_settings.get("brightness", 1.0))

    # Apply Contrast
    img = ImageEnhance.Contrast(img).enhance(image_settings.get("contrast", 1.0))

    # Apply Saturation (Color)
    img = ImageEnhance.Color(img).enhance(image_settings.get("saturation", 1.0))

    # Apply Sharpness
    img = ImageEnhance.Sharpness(img).enhance(image_settings.get("sharpness", 1.0))

    return img

def compute_image_hash(image):
    """Compute SHA-256 hash of an image."""
    image = image.convert("RGB")
    img_bytes = image.tobytes()
    return hashlib.sha256(img_bytes).hexdigest()

def take_screenshot_html(html_str, dimensions, timeout_ms=None):
    image = None
    try:
        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as html_file:
            html_file.write(html_str.encode("utf-8"))
            html_file_path = html_file.name

        image = take_screenshot(html_file_path, dimensions, timeout_ms)

        # Remove html file
        os.remove(html_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image

def _find_chromium_binary():
    """Find the first available Chromium-based binary in system PATH."""
    candidates = ["chromium-headless-shell", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            logger.debug(f"Found browser binary: {candidate} at {path}")
            return candidate
    return None


def take_screenshot(target, dimensions, timeout_ms=None):
    image = None
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": dimensions[0], "height": dimensions[1]},
                device_scale_factor=1
            )
            page = context.new_page()
            
            # Determine if target is a file path or HTML content
            if os.path.exists(target) and (target.endswith('.html') or target.endswith('.htm')):
                page.goto(f"file://{os.path.abspath(target)}", wait_until="networkidle", timeout=30000)
            elif target.startswith("http://") or target.startswith("https://"):
                page.goto(target, wait_until="networkidle", timeout=30000)
            else:
                # Target is HTML content
                page.set_content(target, wait_until="networkidle", timeout=30000)
            
            # Wait for fonts to load
            page.wait_for_timeout(1000)
            
            # Force document height to match viewport
            page.evaluate(f"""
                document.documentElement.style.height = '{dimensions[1]}px';
                document.body.style.height = '{dimensions[1]}px';
                document.body.style.overflow = 'hidden';
            """)
            
            # Wait for layout to update
            page.wait_for_timeout(500)
            
            # Take screenshot with exact dimensions
            screenshot_bytes = page.screenshot(
                clip={"x": 0, "y": 0, "width": dimensions[0], "height": dimensions[1]}
            )
            
            image = Image.open(BytesIO(screenshot_bytes)).copy()
            
            browser.close()

    except ImportError:
        logger.warning("Playwright not available, falling back to Chrome CLI")
        return _take_screenshot_cli(target, dimensions, timeout_ms)
    except Exception as e:
        logger.error(f"Playwright screenshot failed: {e}")
        try:
            return _take_screenshot_cli(target, dimensions, timeout_ms)
        except Exception as e2:
            logger.error(f"CLI fallback also failed: {e2}")
            return None

    return image

def _take_screenshot_cli(target, dimensions, timeout_ms=None):
    """Fallback screenshot using Chrome CLI."""
    image = None
    try:
        browser = _find_chromium_binary()
        if not browser:
            logger.error("No Chromium-based browser found.")
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
            img_file_path = img_file.name

        command = [
            browser,
            target,
            "--headless",
            f"--screenshot={img_file_path}",
            f"--window-size={dimensions[0]},{dimensions[1]}",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-sandbox",
            "--single-process",
            "--no-zygote",
            "--disable-gpu-compositing",
            "--force-device-scale-factor=1",
            "--disable-features=PaintHolding,VizDisplayCompositor",
        ]
        result = subprocess.run(command, capture_output=True, timeout=60)

        if result.returncode != 0 or not os.path.exists(img_file_path):
            logger.error(f"Failed to take screenshot (return code: {result.returncode})")
            return None

        with Image.open(img_file_path) as img:
            image = img.copy()

        os.remove(img_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image

def pad_image_blur(img: Image, dimensions: tuple[int, int]) -> Image:
    bkg = ImageOps.fit(img, dimensions)
    bkg = bkg.filter(ImageFilter.BoxBlur(8))
    img = ImageOps.contain(img, dimensions)

    img_size = img.size
    bkg.paste(img, ((dimensions[0] - img_size[0]) // 2, (dimensions[1] - img_size[1]) // 2))
    return bkg
