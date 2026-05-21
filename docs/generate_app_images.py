#!/usr/bin/env python3
"""Generate manual images using the actual InkyPi application code.
Run from project root: python3 docs/generate_app_images.py"""

from __future__ import annotations
import sys, os, json, logging

logging.basicConfig(level=logging.WARNING)

# --- bootstrap paths ---
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # docs/.. = project root
SRC = os.path.join(PROJECT, "src")
sys.path.insert(0, os.path.abspath(SRC))
os.environ["SRC_DIR"] = os.path.abspath(SRC)

OUT = os.path.join(PROJECT, "docs", "img")
os.makedirs(OUT, exist_ok=True)

# --- mock hardware modules (no real e-ink display attached) ---
class MockInkyDisplay:
    def __init__(self, resolution):
        self.resolution = resolution
        self.id = "mock"
    def set_border(self, color):
        pass
    def set_image(self, img):
        pass
    def show(self):
        pass

class MockDisplayManager:
    def __init__(self, device_config):
        self.device_config = device_config
    def display_image(self, image, image_settings=None):
        pass
    def display_type(self):
        return "mock"

# Install mock before anything imports real inky
import types
inky_mod = types.ModuleType("inky")
inky_mod.InkyDisplayManager = MockDisplayManager
inky_mod.InkyDisplay = MockInkyDisplay
sys.modules["inky"] = inky_mod

# Also mock the display module if it imports inky
sys.modules["display"] = types.ModuleType("display")

# --- now import real app modules ---
from config import Config
from plugins.plugin_registry import load_plugins, get_plugin_instance
from utils.design_variants import get_variant
from PIL import Image, ImageFont

# --- create a minimal mock config for plugin rendering ---
class MockConfig(Config):
    """Override config to work without a real device.json or hardware."""

    def __init__(self):
        # Don't call super().__init__() — we define everything inline
        self.config = {
            "resolution": [800, 480],
            "orientation": "horizontal",
            "design_style": "wa",
            "timezone": "Asia/Tokyo",
            "time_format": "24h",
            "display_type": "mock",
            "calendarURL": "",
            "latitude": 34.69,
            "longitude": 135.50,
            "image_settings": {
                "saturation": 1.0,
                "brightness": 1.0,
                "sharpness": 1.0,
                "contrast": 1.0,
            },
        }
        self.config_file = os.devnull
        self.current_image_file = os.devnull
        self.plugin_image_dir = os.path.join(SRC, "static", "images", "plugins")
        self.refresh_info = None

    def read_config(self):
        return self.config

    def get_config(self, key=None, default=None):
        if key is None:
            return self.config
        return self.config.get(key, default)

    def get_resolution(self):
        return (int(self.config["resolution"][0]), int(self.config["resolution"][1]))

    def get_playlist_manager(self):
        return None

    def get_refresh_info(self):
        return type("obj", (object,), {"get_refresh_datetime": lambda: None, "image_hash": ""})()

    def get_plugins(self):
        return []

    def load_env_key(self, key):
        return os.getenv(key, "")


def _make_minimal_device_config():
    """Load a real device.json if it exists, otherwise use mock."""
    real_path = os.path.join(SRC, "config", "device.json")
    if os.path.exists(real_path):
        dc = Config()
        dc.config_file = real_path
        dc.config = dc.read_config()
        return dc
    return MockConfig()


# --- register plugins ---

def _register_plugin(plugin_id, plugin_class_name=None):
    """Manually register a single plugin so get_plugin_instance works."""
    from plugins.plugin_registry import PLUGIN_CLASSES
    import importlib

    try:
        module = importlib.import_module(f"plugins.{plugin_id}.{plugin_id}")
        if plugin_class_name is None:
            # Try common class names
            for candidate in [plugin_id.replace("_", " ").title().replace(" ", ""),
                              plugin_id.upper().replace("_", ""),
                              plugin_id]:
                if hasattr(module, candidate):
                    plugin_class_name = candidate
                    break
        if plugin_class_name is None:
            # Try to find the class dynamically
            for name in dir(module):
                if name[0].isupper() and name != "BasePlugin":
                    plugin_class_name = name
                    break
        if plugin_class_name:
            cls = getattr(module, plugin_class_name)
            config = {"id": plugin_id, "name": plugin_id, "class": plugin_class_name}
            PLUGIN_CLASSES[plugin_id] = cls(config)
            print(f"  Registered plugin: {plugin_id} -> {plugin_class_name}")
            return True
    except Exception as e:
        print(f"  Failed to register {plugin_id}: {e}")
        return False


# --- image generators ---

def gen_plugin_card(plugin_id, settings=None, output_name=None):
    """Generate a plugin card image using the real plugin code."""
    if output_name is None:
        output_name = f"{plugin_id}.jpg"

    try:
        if plugin_id not in sys.modules.get("plugins.plugin_registry", type(sys)("d")).__dict__:
            _register_plugin(plugin_id)
        plugin = get_plugin_instance({"id": plugin_id})
    except Exception as e:
        print(f"  Cannot load plugin {plugin_id}: {e}")
        return False

    dc = _make_minimal_device_config()

    try:
        img = plugin.generate_image(settings or {}, dc)
        if isinstance(img, Image.Image):
            path = os.path.join(OUT, output_name)
            img.save(path, quality=92)
            print(f"  Saved {output_name} ({img.size})")
            return True
        else:
            print(f"  Plugin {plugin_id} returned non-image: {type(img)}")
            return False
    except Exception as e:
        import traceback
        print(f"  Plugin {plugin_id} generate_image failed: {e}")
        traceback.print_exc()
        return False


def gen_web_screenshot(template_name, output_name, context=None):
    """Render a Flask template to an image using WeasyPrint (approximate)."""
    try:
        from flask import Flask, render_template_string
        import weasyprint
    except ImportError as e:
        print(f"  Cannot render web UI: {e}")
        return False

    # Create a minimal Flask app to render templates
    app = Flask(__name__)
    app.config["SERVER_NAME"] = "inkypi.local"
    app.jinja_options = {"extensions": ["jinja2.ext.do"]}

    # Template path
    template_dir = os.path.join(SRC, "templates")
    env = app.jinja_env
    env.loader.searchpath = [template_dir] if hasattr(env.loader, "searchpath") else None

    with app.app_context():
        try:
            from flask import render_template
            ctx = context or {}

            # We can't easily render full templates with all their includes and
            # url_for calls. Instead, let's just note this limitation.
            print(f"  Cannot render {template_name}: Flask templates require app context with blueprints")
            print(f"  Using PIL-generated approximation instead")
            return False
        except Exception as e:
            print(f"  Failed: {e}")
            return False


# --- generate all images ---

def main():
    print("=== Generating InkyPi manual images ===\n")

    # 1. Plugin cards that render reliably via PIL
    print("Plugin cards:")

    # Morning Briefing — uses PIL fallback
    gen_plugin_card("morning_briefing", output_name="plugins.jpg")

    # Weather — try real plugin first, fall back to PIL
    weather_ok = gen_plugin_card("weather", {
        "latitude": "34.69",
        "longitude": "135.50",
        "units": "metric",
        "weatherProvider": "OpenMeteo",
        "designStyle": "ryoku",
        "customTitle": "\u5929\u6c17",
    }, output_name="weather.jpg")
    if not weather_ok:
        print("  Weather plugin failed — drawing PIL fallback")
        _gen_weather_card(os.path.join(OUT, "weather.jpg"))

    # Evening card — PIL-based
    gen_plugin_card("evening_card", output_name="evening.jpg")

    # Calendar interrupt — can't register as normal plugin; draw directly
    print("\nSpecial cards:")
    _gen_calendar_interrupt(os.path.join(OUT, "interrupt.jpg"))

    # 2. Web UI screenshots — drawn with PIL in app style
    print("\nWeb UI screenshots:")
    _gen_dashboard(os.path.join(OUT, "dashboard.jpg"))
    _gen_schedule(os.path.join(OUT, "schedule.jpg"))

    # 3. Physical device placeholder images
    print("\nPhysical device images (replace with real photos):")
    for name in ["hero", "contents", "parts", "setup"]:
        _gen_placeholder(os.path.join(OUT, f"{name}.jpg"), name)

    print("\nDone.")


# --- fallback PIL renderers for things that can't use real plugin code ---

def _gen_calendar_interrupt(path):
    from utils.design_variants import get_variant
    from utils.app_utils import get_font
    from PIL import Image, ImageDraw

    v = get_variant("ima")
    C = v.colors
    W, H = 800, 480

    img = Image.new("RGB", (W, H), C["bg"])
    d = ImageDraw.Draw(img)

    f_label = get_font(v.body_font, int(W * 0.028)) or ImageFont.load_default()
    f_title = get_font(v.heading_font, int(W * 0.05)) or ImageFont.load_default()
    f_time = get_font(v.body_font, int(W * 0.03)) or ImageFont.load_default()
    f_date = get_font(v.body_font, int(W * 0.018)) or ImageFont.load_default()

    cx = W // 2
    label = "\u6b21\u306e\u4e88\u5b9a"
    bb = d.textbbox((0, 0), label, font=f_label)
    d.text((cx - (bb[2] - bb[0]) // 2, int(H * 0.28)), label, font=f_label, fill=C["accent"])

    title = "\u4f1a\u8b70 \u2014 \u56db\u5e83\u30d7\u30ed\u30b8\u30a7\u30af\u30c8"
    bb = d.textbbox((0, 0), title, font=f_title)
    tw = bb[2] - bb[0]
    if tw > W * 0.8:
        f_title = get_font(v.heading_font, int(W * 0.038)) or f_title
        bb = d.textbbox((0, 0), title, font=f_title)
        tw = bb[2] - bb[0]
    d.text((cx - tw // 2, int(H * 0.37)), title, font=f_title, fill=C["text_primary"])

    dy = int(H * 0.48)
    dw = int(W * 0.12)
    d.line([(cx - dw, dy), (cx + dw, dy)], fill=C["divider"], width=v.divider_width * 2)

    time_str = "15\u5206\u5f8c"
    bb = d.textbbox((0, 0), time_str, font=f_time)
    d.text((cx - (bb[2] - bb[0]) // 2, int(H * 0.53)), time_str, font=f_time, fill=C["text_secondary"])

    date_str = "5\u670821\u65e5"
    bb = d.textbbox((0, 0), date_str, font=f_date)
    d.text((W - int(W * 0.05) - (bb[2] - bb[0]), int(H * 0.92)), date_str, font=f_date, fill=C["text_light"])

    img.save(path, quality=92)
    print(f"  Saved interrupt.jpg")


def _gen_dashboard(path):
    """Draw a phone UI mockup that looks like the real dashboard."""
    from PIL import Image, ImageDraw, ImageFont
    from utils.app_utils import get_font

    PW, PH = 390, 844

    def f(name, size):
        ft = get_font(name, size)
        return ft or ImageFont.load_default()

    img = Image.new("RGB", (PW, PH), (245, 245, 245))
    d = ImageDraw.Draw(img)

    # White card
    d.rectangle([(8, 8), (PW - 9, PH - 9)], fill=(255, 255, 255))

    # Header bar
    d.rectangle([(8, 8), (PW - 9, 44)], fill=(26, 188, 156))
    d.text((20, 16), "9:41", font=f("Jost", 14), fill=(255, 255, 255))
    d.text((PW - 130, 16), "InkyPi", font=f("Jost", 16), fill=(255, 255, 255))

    # Nav links
    nav = [("Dashboard", True), ("Photos", False), ("Mode", False), ("Settings", False)]
    nx = 20
    for label, active in nav:
        fc = (26, 188, 156) if active else (140, 140, 140)
        d.text((nx, 54), label, font=f("Noto Sans JP", 11), fill=fc)
        bb = d.textbbox((0, 0), label, font=f("Noto Sans JP", 11))
        nx += bb[2] - bb[0] + 16

    # Clock
    cf = f("Jost", 48)
    d.text((PW // 2 - 60, 84), "10:24", font=cf, fill=(50, 50, 50))

    # Status
    d.text((PW // 2 - 38, 138), "Now Showing", font=f("Noto Sans JP", 9), fill=(160, 160, 160))
    d.text((PW // 2 - 50, 152), "Morning Briefing", font=f("Noto Sans JP", 12), fill=(26, 188, 156))

    # Mode badge
    bx, by = PW // 2 - 48, 172
    d.rectangle([(bx, by), (bx + 96, by + 20)], fill=(26, 188, 156))
    d.text((bx + 14, by + 3), "Scheduled", font=f("Noto Sans JP", 9), fill=(255, 255, 255))

    # Fake display preview
    px, py = 40, 204
    d.rectangle([(px, py), (PW - 40, py + 150)], fill=(235, 240, 235), outline=(210, 215, 210))
    mini = Image.new("RGB", (PW - 80, 150), (235, 240, 235))
    from PIL import ImageDraw as MiniDraw
    md = MiniDraw.Draw(mini)
    # Draw a mini morning briefing inside
    md.rectangle([(10, 5), (PW - 100, 20)], fill=(26, 188, 156))
    md.text((20, 38), "Good Morning", font=f("Noto Sans JP", 14), fill=(60, 60, 60))
    md.text((20, 60), "22°  Sunny", font=f("Noto Sans JP", 11), fill=(100, 100, 100))
    md.text((20, 82), "10:00  Meeting", font=f("Noto Sans JP", 9), fill=(140, 140, 140))
    img.paste(mini, (px, py))

    # Schedule section
    sy = py + 168
    d.text((20, sy), "Today's Schedule", font=f("Noto Sans JP", 14), fill=(50, 50, 50))

    items = [
        ("Morning Briefing", "06:30 - 07:30", True),
        ("Photos + Info",   "07:30 - 12:00", False),
        ("Weather Detail",  "12:00 - 12:30", False),
        ("Painting",        "14:30 - 14:45", False),
        ("Evening Card",    "18:00 - 18:30", False),
    ]
    iy = sy + 28
    for name, time, active in items:
        if active:
            d.rectangle([(16, iy), (PW - 16, iy + 38)], fill=(26, 188, 156))
            d.text((28, iy + 5), name, font=f("Noto Sans JP", 11), fill=(255, 255, 255))
            d.text((28, iy + 20), time, font=f("Noto Sans JP", 9), fill=(200, 245, 235))
            d.rectangle([(PW - 72, iy + 6), (PW - 28, iy + 32)], fill=(255, 255, 255))
            d.text((PW - 64, iy + 11), "NOW", font=f("Noto Sans JP", 7), fill=(26, 188, 156))
        else:
            d.text((28, iy + 5), name, font=f("Noto Sans JP", 11), fill=(80, 80, 80))
            d.text((28, iy + 20), time, font=f("Noto Sans JP", 9), fill=(160, 160, 160))
        iy += 42

    img.save(path, quality=92)
    print(f"  Saved dashboard.jpg")


def _gen_schedule(path):
    """Draw a phone UI of the settings page with schedule editor."""
    from PIL import Image, ImageDraw, ImageFont
    from utils.app_utils import get_font

    PW, PH = 390, 844

    def f(name, size):
        ft = get_font(name, size)
        return ft or ImageFont.load_default()

    img = Image.new("RGB", (PW, PH), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Status bar
    d.rectangle([(0, 0), (PW, 36)], fill=(26, 188, 156))
    d.text((16, 10), "9:41", font=f("Jost", 14), fill=(255, 255, 255))

    # Title
    d.text((16, 46), "Settings", font=f("Jost", 20), fill=(50, 50, 50))

    # Nav
    for i, lbl in enumerate(["Dashboard", "Photos", "Mode"]):
        x = PW - 200 + i * 72
        d.text((x, 50), lbl, font=f("Noto Sans JP", 10), fill=(120, 120, 120))

    # --- Design Style ---
    d.text((16, 88), "Design Style", font=f("Noto Sans JP", 14), fill=(50, 50, 50))
    d.text((16, 106), "Choose visual style for cards", font=f("Noto Sans JP", 9), fill=(160, 160, 160))

    styles = [
        ("Wa",   (240, 232, 215), (26, 188, 156)),
        ("Zen",  (245, 245, 245), (180, 180, 180)),
        ("Ryoku",(252, 245, 235), (220, 80, 60)),
        ("Ima",  (235, 242, 248), (100, 150, 200)),
    ]
    sx = 16
    for label, bg, accent in styles:
        d.rectangle([(sx, 122), (sx + 82, 172)], fill=bg, outline=(215, 215, 215))
        d.line([(sx + 6, 130), (sx + 76, 130)], fill=accent, width=2)
        d.rectangle([(sx + 6, 136), (sx + 22, 150)], fill=accent)
        d.text((sx + 28, 152), label, font=f("Noto Sans JP", 8), fill=(100, 100, 100))
        sx += 90

    # --- Photos ---
    d.text((16, 192), "Photos", font=f("Noto Sans JP", 14), fill=(50, 50, 50))
    d.text((16, 210), "How often to switch photos", font=f("Noto Sans JP", 9), fill=(160, 160, 160))
    d.text((16, 228), "Every  5    Minute", font=f("Noto Sans JP", 11), fill=(100, 100, 100))

    # --- Calendar ---
    d.text((16, 262), "Calendar", font=f("Noto Sans JP", 14), fill=(50, 50, 50))
    d.rectangle([(16, 280), (PW - 16, 302)], fill=(245, 245, 245), outline=(220, 220, 220))
    d.text((22, 284), "https://calendar.google.com/...", font=f("Noto Sans JP", 9), fill=(160, 160, 160))

    # --- Daily Schedule collapsible header ---
    dsy = 322
    d.rectangle([(12, dsy), (PW - 12, dsy + 34)], fill=(237, 235, 235), outline=(220, 220, 220))
    d.text((22, dsy + 9), "Daily Schedule", font=f("Noto Sans JP", 13), fill=(50, 50, 50))
    d.text((PW - 36, dsy + 9), "\u25bc", font=f("Noto Sans JP", 10), fill=(120, 120, 120))

    # --- Mode rows ---
    modes = [
        ("Morning",     ["mon","tue","wed","thu","fri"], "06:30", "07:30", "Card"),
        ("Photos + Info",["mon","tue","wed","thu","fri","sat","sun"], "07:30", "18:00", "Photos"),
        ("Evening Card", ["mon","tue","wed","thu","fri","sat","sun"], "18:00", "18:30", "Card"),
    ]

    ry = dsy + 44
    for name, days, st, et, mtype in modes:
        d.rectangle([(12, ry), (PW - 12, ry + 82)], fill=(252, 252, 252), outline=(225, 225, 225))

        d.text((22, ry + 4), name, font=f("Noto Sans JP", 12), fill=(50, 50, 50))
        d.text((PW - 46, ry + 4), "\u2715", font=f("Noto Sans JP", 12), fill=(200, 60, 60))

        day_order = ["mon","tue","wed","thu","fri","sat","sun"]
        dx = 22
        for dl in day_order:
            c = (26, 188, 156) if dl in days else (180, 180, 180)
            d.text((dx, ry + 26), dl, font=f("Noto Sans JP", 8), fill=c)
            dx += 26

        d.text((22, ry + 44), f"Start {st}", font=f("Noto Sans JP", 8), fill=(100, 100, 100))
        d.text((120, ry + 44), f"End {et}", font=f("Noto Sans JP", 8), fill=(100, 100, 100))
        d.text((220, ry + 44), "300 sec", font=f("Noto Sans JP", 8), fill=(100, 100, 100))

        mc = (26, 188, 156) if mtype == "Card" else (140, 68, 180)
        d.text((22, ry + 62), f"Type: {mtype}", font=f("Noto Sans JP", 8), fill=mc)
        if mtype == "Card":
            d.text((100, ry + 62), "morning_briefing", font=f("Noto Sans JP", 8), fill=(120, 120, 120))
        else:
            d.text((100, ry + 62), "pool: 6 cards", font=f("Noto Sans JP", 8), fill=(120, 120, 120))
        ry += 90

    # Add button
    d.rectangle([(12, ry + 4), (PW - 12, ry + 30)], fill=(245, 245, 245), outline=(220, 220, 220))
    d.text((PW // 2 - 36, ry + 10), "+ Add Time Slot", font=f("Noto Sans JP", 10), fill=(100, 100, 100))

    # Save button
    d.rectangle([(16, PH - 50), (PW - 16, PH - 20)], fill=(26, 188, 156))
    d.text((PW // 2 - 16, PH - 42), "Save", font=f("Noto Sans JP", 13), fill=(255, 255, 255))

    img.save(path, quality=92)
    print(f"  Saved schedule.jpg")


def _gen_weather_card(path):
    """PIL fallback: draw a weather card matching the real design."""
    from utils.design_variants import get_variant
    from utils.app_utils import get_font
    from PIL import Image, ImageDraw

    v = get_variant("ryoku")
    C = v.colors
    W, H = 800, 480

    img = Image.new("RGB", (W, H), C["bg"])
    d = ImageDraw.Draw(img)

    f_day = get_font(v.heading_font, int(W * 0.048)) or ImageFont.load_default()
    f_temp = get_font(v.body_font, int(W * 0.07)) or ImageFont.load_default()
    f_label = get_font(v.body_font, int(W * 0.022)) or ImageFont.load_default()
    f_cond = get_font(v.body_font, int(W * 0.025)) or ImageFont.load_default()
    f_small = get_font(v.body_font, int(W * 0.018)) or ImageFont.load_default()

    # Date/header
    date_str = "2026\u5e745\u670821\u65e5 (\u6728)"
    bb = d.textbbox((0, 0), date_str, font=f_day)
    d.text((W // 2 - (bb[2] - bb[0]) // 2, int(H * 0.06)), date_str, font=f_day, fill=C["text_primary"])

    # Divider
    dw = int(W * 0.15)
    d.line([(W // 2 - dw, int(H * 0.14)), (W // 2 + dw, int(H * 0.14))], fill=C["divider"], width=v.divider_width)

    # Large temperature
    temp_str = "22\xb0"
    bb = d.textbbox((0, 0), temp_str, font=f_temp)
    d.text((W // 2 - (bb[2] - bb[0]) // 2, int(H * 0.18)), temp_str, font=f_temp, fill=C["text_primary"])

    # Condition
    cond_str = "\u6674\u308c \u2014 \u592a\u967d"
    bb = d.textbbox((0, 0), cond_str, font=f_cond)
    d.text((W // 2 - (bb[2] - bb[0]) // 2, int(H * 0.28)), cond_str, font=f_cond, fill=C["text_secondary"])

    # Feels like
    feels_str = "\u4f53\u611f\u6e29\u5ea6 20\xb0"
    bb = d.textbbox((0, 0), feels_str, font=f_label)
    d.text((W // 2 - (bb[2] - bb[0]) // 2, int(H * 0.34)), feels_str, font=f_label, fill=C["text_light"])

    # Data points row
    data = [
        ("\u6fd5\u5ea6", "62%"),
        ("\u98a8", "4m/s"),
        ("UV", "3"),
        ("\u6c5e\u538b", "1015hPa"),
    ]
    section_w = int(W * 0.7)
    start_x = (W - section_w) // 2
    gap = section_w // len(data)
    for i, (label, val) in enumerate(data):
        x = start_x + i * gap + gap // 2
        d.text((x - 20, int(H * 0.44)), val, font=f_label, fill=C["text_primary"])
        d.text((x - 18, int(H * 0.49)), label, font=f_small, fill=C["text_light"])

    # Divider
    d.line([(int(W * 0.08), int(H * 0.55)), (int(W * 0.92), int(H * 0.55))], fill=C["divider"], width=v.divider_width)

    # Hourly forecast row
    d.text((int(W * 0.08), int(H * 0.57)), "\u6642\u9593\u5f53\u4e88\u5831", font=f_label, fill=C["text_light"])
    hours = [
        ("10:00", "\u6674\u308c", "22\xb0"),
        ("11:00", "\u6674\u308c", "23\xb0"),
        ("12:00", "\u6674\u308c", "24\xb0"),
        ("13:00", "\u66c7\u308a", "24\xb0"),
        ("14:00", "\u66c7\u308a", "25\xb0"),
    ]
    hx = int(W * 0.08)
    for htime, hcond, htemp in hours:
        d.text((hx, int(H * 0.63)), htemp, font=f_small, fill=C["text_primary"])
        d.text((hx, int(H * 0.67)), hcond, font=f_small, fill=C["text_light"])
        d.text((hx, int(H * 0.71)), htime, font=f_small, fill=C["text_light"])
        hx += int(W * 0.17)

    # 7-day forecast header
    d.line([(int(W * 0.08), int(H * 0.78)), (int(W * 0.92), int(H * 0.78))], fill=C["divider"], width=v.divider_width)
    d.text((int(W * 0.08), int(H * 0.80)), "7\u65e5\u9593\u4e88\u5831", font=f_label, fill=C["text_light"])

    days = [
        ("\u6728", "\u6674\u308c", "22/14"),
        ("\u91d1", "\u6674\u308c", "24/15"),
        ("\u571f", "\u66c7\u308a", "23/16"),
        ("\u65e5", "\u96e8", "19/13"),
        ("\u6708", "\u6674\u308c", "21/14"),
        ("\u706b", "\u6674\u308c", "22/15"),
        ("\u6c34", "\u66c7\u308a", "21/15"),
    ]
    dx = int(W * 0.08)
    for dlabel, dcond, dtemp in days:
        d.text((dx, int(H * 0.86)), dlabel, font=f_label, fill=C["text_primary"])
        d.text((dx, int(H * 0.90)), dcond, font=f_small, fill=C["text_light"])
        d.text((dx, int(H * 0.94)), dtemp, font=f_small, fill=C["text_light"])
        dx += int(W * 0.12)

    img.save(path, quality=92)
    print(f"  Saved weather.jpg (PIL fallback)")


def _gen_placeholder(path, label):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (800, 600), (225, 225, 225))
    d = ImageDraw.Draw(img)
    ft = ImageFont.load_default()
    d.text((300, 280), f"[ {label} -- photograph needed ]", font=ft, fill=(140, 140, 140))
    img.save(path, quality=85)
    print(f"  Placeholder {label}.jpg")


if __name__ == "__main__":
    main()
