import threading
import time
import random
import logging
from flask import Blueprint, request, jsonify, current_app, render_template, send_file
from refresh_task import CalendarInterrupt, WeatherAlertInterrupt
from plugins.plugin_registry import get_plugin_instance
from PIL import Image, ImageDraw
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)

_demo_thread = None
_demo_stop = threading.Event()

@main_bp.route('/')
def main_page():
    device_config = current_app.config['DEVICE_CONFIG']
    return render_template('inky.html', config=device_config.get_config(), plugins=device_config.get_plugins())

@main_bp.route('/api/current_image')
def get_current_image():
    """Serve current_image.png with conditional request support (If-Modified-Since)."""
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images', 'current_image.png')
    
    if not os.path.exists(image_path):
        return jsonify({"error": "Image not found"}), 404
    
    # Get the file's last modified time (truncate to seconds to match HTTP header precision)
    file_mtime = int(os.path.getmtime(image_path))
    last_modified = datetime.fromtimestamp(file_mtime)
    
    # Check If-Modified-Since header
    if_modified_since = request.headers.get('If-Modified-Since')
    if if_modified_since:
        try:
            # Parse the If-Modified-Since header
            client_mtime = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S %Z')
            client_mtime_seconds = int(client_mtime.timestamp())
            
            # Compare (both now in seconds, no sub-second precision)
            if file_mtime <= client_mtime_seconds:
                return '', 304
        except (ValueError, AttributeError):
            pass
    
    # Send the file with Last-Modified header
    response = send_file(image_path, mimetype='image/png')
    response.headers['Last-Modified'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
    response.headers['Cache-Control'] = 'no-cache'
    return response


@main_bp.route('/api/plugin_order', methods=['POST'])
def save_plugin_order():
    """Save the custom plugin order."""
    device_config = current_app.config['DEVICE_CONFIG']

    data = request.get_json() or {}
    order = data.get('order', [])

    if not isinstance(order, list):
        return jsonify({"error": "Order must be a list"}), 400

    device_config.set_plugin_order(order)

    return jsonify({"success": True})


@main_bp.route('/api/preview/calendar_interrupt')
def preview_calendar_interrupt():
    """Preview a calendar interrupt notification card."""
    device_config = current_app.config['DEVICE_CONFIG']
    display_manager = current_app.config['DISPLAY_MANAGER']

    event_data = {
        "title": "Team Standup",
        "minutes_until": 5,
    }
    interrupt = CalendarInterrupt(event_data)
    image = interrupt.execute(None, device_config, datetime.now())
    display_manager.display_image(image)
    return jsonify({"success": True, "message": "Calendar interrupt preview"})


@main_bp.route('/api/preview/weather_alert_interrupt')
def preview_weather_alert():
    """Preview a weather alert notification card."""
    device_config = current_app.config['DEVICE_CONFIG']
    display_manager = current_app.config['DISPLAY_MANAGER']

    alert_data = {
        "event": "Heavy Rain Warning",
        "description": "Heavy rainfall expected in the region. Please take necessary precautions and avoid low-lying areas.",
    }
    interrupt = WeatherAlertInterrupt(alert_data)
    image = interrupt.execute(None, device_config, datetime.now())
    display_manager.display_image(image)
    return jsonify({"success": True, "message": "Weather alert preview"})


PHOTO_DIRS = [
    os.path.expanduser("~/Pictures"),
    os.path.expanduser("~/Photos"),
    os.path.expanduser("~/写真"),
    "/media",
    "/mnt",
]

DEMO_SCHEDULE = [
    ("morning_briefing", 10, "Morning Briefing 06:30"),
    ("photo", 6, "Resting State — Photo"),
    ("weather", 10, "Weather 08:15"),
    ("photo", 6, "Resting State — Photo"),
    ("meal_vocab", 10, "Meal + Portuguese 12:00"),
    ("photo", 6, "Resting State — Photo"),
    ("painting", 10, "Painting 14:30"),
    ("photo", 6, "Resting State — Photo"),
    ("mood_card", 10, "Coffee Break 16:00"),
    ("photo", 6, "Resting State — Photo"),
    ("evening_card", 10, "Evening Card 18:00"),
    ("photo", 6, "Resting State — Photo"),
    ("goodnight_card", 10, "Good Night 21:00"),
    ("kansai_events", 8, "Kansai Events"),
    ("calendar_interrupt", 8, "Calendar Alert"),
    ("weather_alert_interrupt", 8, "Weather Alert"),
]


def _find_random_photo():
    """Pick a random photo from common photo directories."""
    exts = ('.jpg', '.jpeg', '.png', '.avif', '.webp', '.bmp', '.tiff', '.heif', '.heic')
    candidates = []
    for d in PHOTO_DIRS:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(exts) and not f.startswith('.'):
                        candidates.append(os.path.join(root, f))
    if not candidates:
        return None
    return random.choice(candidates)


def _show_plugin(device_config, display_manager, pid):
    """Generate and display a plugin image. Returns an image or None."""
    try:
        if pid == "calendar_interrupt":
            return CalendarInterrupt({"title": "Team Standup", "minutes_until": 5}).execute(None, device_config, datetime.now())
        elif pid == "weather_alert_interrupt":
            return WeatherAlertInterrupt({"event": "Heavy Rain Warning", "description": "Heavy rainfall expected. Please take precautions."}).execute(None, device_config, datetime.now())
        elif pid == "photo":
            path = _find_random_photo()
            if path:
                img = Image.open(path)
                target = device_config.get_resolution()
                if device_config.get_config("orientation") == "vertical":
                    target = target[::-1]
                img = img.resize(target, Image.Resampling.LANCZOS)
                return img.convert("RGB")
            logger.info("Demo: no photos found, falling back to clock")
            pid = "clock"
        plugin_config = device_config.get_plugin(pid)
        if not plugin_config:
            return None
        plugin = get_plugin_instance(plugin_config)
        return plugin.generate_image({}, device_config)
    except Exception as e:
        logger.warning(f"Demo: skipped {pid}: {e}")
        return None


def _demo_cycle(app):
    """Cycles through the daily schedule at 10s intervals to simulate production behavior."""
    with app.app_context():
        device_config = app.config['DEVICE_CONFIG']
        display_manager = app.config['DISPLAY_MANAGER']

        while not _demo_stop.is_set():
            for pid, duration, label in DEMO_SCHEDULE:
                if _demo_stop.is_set():
                    return
                image = _show_plugin(device_config, display_manager, pid)
                if image:
                    display_manager.display_image(image)
                    logger.info(f"Demo: {label} ({pid})")
                if _demo_stop.wait(timeout=duration):
                    return


@main_bp.route('/api/demo/start')
def demo_start():
    """Start cycling through all plugin screens at 10s intervals."""
    global _demo_thread, _demo_stop
    if _demo_thread and _demo_thread.is_alive():
        return jsonify({"success": False, "message": "Demo already running"})
    _demo_stop.clear()
    app = current_app._get_current_object()
    _demo_thread = threading.Thread(target=_demo_cycle, args=(app,), daemon=True)
    _demo_thread.start()
    return jsonify({"success": True, "message": "Demo started"})


@main_bp.route('/api/demo/stop')
def demo_stop():
    """Stop the demo cycle."""
    global _demo_stop
    _demo_stop.set()
    return jsonify({"success": True, "message": "Demo stopped"})


# ---------------------------------------------------------------------------
# Scheduler Simulation Demo
# ---------------------------------------------------------------------------

SCHEDULER_DEMO_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def _draw_overlay(image, lines):
    """Draw multiline demo overlay text on an image.
    lines: list of (text, y_position_ratio) tuples.
    """
    draw = ImageDraw.Draw(image)
    w, h = image.size
    font_size = max(11, int(w * 0.018))
    try:
        from utils.app_utils import get_font
        font = get_font("NotoSansCJK-Regular.ttc", font_size)
    except Exception:
        font = None

    for text, y_ratio in lines:
        y = int(h * y_ratio)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2
        # Black stroke for readability
        for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
    return image


def _sim_fallback_image(device_config, text):
    """Generate a fallback image with text when a plugin fails."""
    w, h = device_config.get_resolution()
    img = Image.new('RGB', (w, h), (240, 240, 235))
    img = _draw_overlay(img, [(text, 0.45)])
    return img


def _scheduler_simulation(app):
    """Walk through all scheduler modes showing new capabilities."""
    with app.app_context():
        try:
            device_config = app.config['DEVICE_CONFIG']
            display_manager = app.config['DISPLAY_MANAGER']
            refresh_task = app.config['REFRESH_TASK']
            scheduler = refresh_task.scheduler
        except Exception as e:
            logger.exception("SchedSim: failed to get app config: %s", e)
            return

        def _time_key(m):
            t = m.get("start_time", "00:00")
            h, m2 = map(int, t.split(":"))
            return h * 60 + m2
        sorted_modes = sorted(scheduler.modes, key=_time_key)

        sim_day = "sat"
        sim_date = datetime(2026, 5, 23, 5, 0)

        # Show starting screen
        w, h = device_config.get_resolution()
        splash = Image.new('RGB', (w, h), (240, 240, 235))
        splash = _draw_overlay(splash, [
            ("SCHEDULER SIMULATION", 0.35),
            (f"{len(scheduler.modes)} modes · Saturday walkthrough", 0.45),
            ("Showing fixed cards, photo resting state,", 0.55),
            ("interstitial cards, and day-of-week matching", 0.62),
        ])
        display_manager.display_image(splash)
        if _demo_stop.wait(timeout=3):
            return

        modes_shown = 0
        for mode in sorted_modes:
            if _demo_stop.is_set():
                return

            days = mode.get("days", [])
            if sim_day not in days:
                continue

            name = mode.get("name", "?")
            plugin_id = mode.get("plugin_id")
            pool = mode.get("interstitial_pool", [])
            start_t = mode.get("start_time", "--:--")

            sh, sm = map(int, start_t.split(":"))
            sim_dt = sim_date.replace(hour=sh, minute=sm)

            overlay_top = f"SCHEDULER SIM  |  {sim_day.upper()} {sim_dt.strftime('%H:%M')}  |  {name}"
            logger.info("SchedSim: %s", overlay_top)

            if plugin_id:
                dwell = mode.get("dwell_seconds", 300)
                overlay_info = f"plugin_id: {plugin_id}  |  dwell: {dwell}s"
                try:
                    image = _show_plugin(device_config, display_manager, plugin_id)
                except Exception as e:
                    logger.warning("SchedSim: %s plugin errored: %s", plugin_id, e)
                    image = None
                if not image:
                    image = _sim_fallback_image(device_config, f"{name}: {plugin_id}")
                image = _draw_overlay(image, [
                    (overlay_top, 0.03),
                    (overlay_info, 0.92),
                ])
                display_manager.display_image(image)
                modes_shown += 1

            elif pool:
                interval = mode.get("interstitial_interval_seconds", 1800)
                dwell = mode.get("dwell_seconds", 300)
                overlay_info = f"photo mode  |  dwell: {dwell}s  |  interstitial every {interval}s"

                # Photo
                path = _find_random_photo()
                if path:
                    try:
                        img = Image.open(path)
                        target = device_config.get_resolution()
                        if device_config.get_config("orientation") == "vertical":
                            target = target[::-1]
                        img = img.resize(target, Image.Resampling.LANCZOS).convert("RGB")
                    except Exception as e:
                        logger.warning("SchedSim: photo load failed: %s", e)
                        img = _sim_fallback_image(device_config, f"{name}: photo resting state")
                else:
                    img = _sim_fallback_image(device_config, f"{name}: photo mode (no photos found)")
                img = _draw_overlay(img, [
                    (overlay_top, 0.03),
                    (f"RESTING STATE — {overlay_info}", 0.92),
                ])
                display_manager.display_image(img)
                modes_shown += 1

                # Interstitial card
                if pool and not _demo_stop.is_set():
                    if _demo_stop.wait(timeout=3):
                        return
                    pool_id = random.choice(pool)
                    pool_overlay = f"Interstitial pool: {', '.join(pool)}  |  picked: {pool_id}"
                    try:
                        card = _show_plugin(device_config, display_manager, pool_id)
                    except Exception as e:
                        logger.warning("SchedSim: interstitial %s errored: %s", pool_id, e)
                        card = None
                    if not card:
                        card = _sim_fallback_image(device_config, f"Interstitial: {pool_id}")
                    card = _draw_overlay(card, [
                        (overlay_top, 0.03),
                        (pool_overlay, 0.92),
                    ])
                    display_manager.display_image(card)
                    modes_shown += 1

            if _demo_stop.wait(timeout=5):
                return

        if not _demo_stop.is_set():
            w, h = device_config.get_resolution()
            summary = Image.new('RGB', (w, h), (240, 240, 235))
            summary = _draw_overlay(summary, [
                ("SCHEDULER SIMULATION COMPLETE", 0.32),
                (f"{modes_shown} cards shown across {len(sorted_modes)} modes", 0.42),
                ("Fixed card slots  ·  Photo resting state", 0.50),
                ("Random interstitial pool  ·  Day-of-week matching", 0.58),
                ("Interrupt queue  ·  Overnight wrapping modes", 0.66),
            ])
            display_manager.display_image(summary)
            logger.info("SchedSim: complete — %d cards shown", modes_shown)


@main_bp.route('/api/demo/scheduler/start')
def scheduler_demo_start():
    """Walk through all scheduler modes showing new capabilities."""
    global _demo_thread, _demo_stop
    if _demo_thread and _demo_thread.is_alive():
        return jsonify({"success": False, "message": "A demo is already running"})
    _demo_stop.clear()
    app = current_app._get_current_object()
    _demo_thread = threading.Thread(target=_scheduler_simulation, args=(app,), daemon=True)
    _demo_thread.start()
    return jsonify({"success": True, "message": "Scheduler simulation started"})


@main_bp.route('/api/scheduler/status')
def scheduler_status():
    """Return current scheduler status for the web UI."""
    device_config = current_app.config['DEVICE_CONFIG']
    refresh_task = current_app.config.get('REFRESH_TASK')
    if not refresh_task:
        return jsonify({"enabled": False, "error": "No refresh task"})
    scheduler = refresh_task.scheduler
    status = scheduler.get_status()
    from datetime import datetime
    import pytz
    tz_str = device_config.get_config("timezone", default="UTC")
    current_dt = datetime.now(pytz.timezone(tz_str))
    active = scheduler.get_active_mode(current_dt)
    status["active_mode"] = active.get("name") if active else None
    status["current_time"] = current_dt.strftime("%a %H:%M")
    return jsonify(status)