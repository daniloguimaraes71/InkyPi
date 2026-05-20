import os
import json
import logging
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, render_template, send_from_directory
from refresh_task import ManualRefresh, PhotoRefresh
from PIL import Image
from werkzeug.utils import secure_filename
from utils.design_variants import VARIANTS

logger = logging.getLogger(__name__)
user_bp = Blueprint("user", __name__)

PHOTO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images", "user_photos")
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.avif', '.webp', '.bmp', '.tiff', '.heif', '.heic'}


def _ensure_photo_dir():
    os.makedirs(PHOTO_DIR, exist_ok=True)


def _allowed_file(filename):
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


@user_bp.route('/')
def user_dashboard():
    device_config = current_app.config['DEVICE_CONFIG']
    return render_template('user_dashboard.html', config=device_config.get_config())


@user_bp.route('/photos')
def user_photos():
    return render_template('user_photos.html')


@user_bp.route('/mode-select')
def user_mode_select():
    device_config = current_app.config['DEVICE_CONFIG']
    current_mode = device_config.get_config("user_display_mode", default="scheduled")
    return render_template('user_mode_select.html', current_mode=current_mode)


@user_bp.route('/user-settings')
def user_settings():
    device_config = current_app.config['DEVICE_CONFIG']
    current_style = device_config.get_config("design_style", default="wa")
    calendar_url = device_config.get_config("calendarURL", default="")
    photos_interval = device_config.get_config("photos_interval_seconds", default=300)
    styles = []
    for v in VARIANTS.values():
        styles.append({
            "name": v.name,
            "label": v.label,
            "description": v.description,
            "colors": v.colors,
        })
    return render_template('user_settings.html', design_styles=styles, current_style=current_style, calendar_url=calendar_url, photos_interval=photos_interval)


@user_bp.route('/api/user/settings', methods=['POST'])
def save_user_settings():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    device_config = current_app.config['DEVICE_CONFIG']

    if "design_style" in data:
        style = data["design_style"]
        if style not in VARIANTS:
            return jsonify({"error": f"Invalid design style: {style}"}), 400
        device_config.update_value("design_style", style, write=True)

    if "calendarURL" in data:
        device_config.update_value("calendarURL", data["calendarURL"], write=True)

    if "photos_interval_seconds" in data:
        device_config.update_value("photos_interval_seconds", data["photos_interval_seconds"], write=True)

    refresh_task = current_app.config.get('REFRESH_TASK')
    if refresh_task:
        refresh_task.signal_config_change()

    return jsonify({"success": True})


@user_bp.route('/api/user/display-mode', methods=['GET'])
def get_display_mode():
    device_config = current_app.config['DEVICE_CONFIG']
    current = device_config.get_config("user_display_mode", default="scheduled")
    return jsonify({"mode": current})


@user_bp.route('/api/user/display-mode', methods=['POST'])
def set_display_mode():
    data = request.get_json()
    mode = data.get("mode") if data else None
    valid_modes = ("scheduled", "clock_only", "photos_only", "calendar_month", "calendar_week", "calendar_day")
    if mode not in valid_modes:
        return jsonify({"error": "Invalid mode, must be: scheduled, clock_only, photos_only"}), 400

    device_config = current_app.config['DEVICE_CONFIG']
    device_config.update_value("user_display_mode", mode, write=True)
    logger.info("User display mode set to: %s", mode)

    refresh_task = current_app.config.get('REFRESH_TASK')
    if refresh_task:
        refresh_task.signal_config_change()

    return jsonify({"success": True, "mode": mode})


@user_bp.route('/api/user/status')
def user_status():
    device_config = current_app.config['DEVICE_CONFIG']
    refresh_task = current_app.config.get('REFRESH_TASK')
    tz_str = device_config.get_config("timezone", default="UTC")
    current_dt = datetime.now(pytz.timezone(tz_str))

    user_mode = device_config.get_config("user_display_mode", default="scheduled")
    status = {"enabled": False, "current_mode": None, "current_time": current_dt.strftime("%a %H:%M"), "user_display_mode": user_mode, "modes": []}

    scheduler = refresh_task.scheduler if refresh_task and hasattr(refresh_task, 'scheduler') else None
    if scheduler and scheduler.is_enabled():
        active = scheduler.get_active_mode(current_dt)
        s = scheduler.get_status()
        status.update({
            "enabled": True,
            "current_mode": active.get("name") if active else s.get("current_mode"),
            "forced_mode": s.get("forced_mode"),
            "modes_count": s.get("modes_count"),
        })

    status["modes"] = _build_mode_list(current_dt, device_config)
    return jsonify(status)


def _build_mode_list(current_dt, device_config):
    """Return today's modes with name, time window, and whether active."""
    scheduler_cfg = device_config.get_config("scheduler", default={})
    modes = scheduler_cfg.get("modes", [])
    day_key = current_dt.strftime("%a").lower()
    current_time = current_dt.strftime("%H:%M")

    result = []
    for m in modes:
        days = m.get("days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
        if day_key not in days:
            continue
        start = m.get("start_time", "00:00")
        end = m.get("end_time", "24:00")
        is_active = _is_in_window(current_time, start, end)
        name = m.get("name", "unknown")
        display_name = name.replace("_", " ").title()
        plugin_id = m.get("plugin_id")
        pool = m.get("interstitial_pool", [])
        is_photo_mode = bool(pool) or (not plugin_id)
        result.append({
            "name": name,
            "display_name": display_name,
            "start_time": start,
            "end_time": end,
            "is_active": is_active,
            "is_photo_mode": is_photo_mode,
            "plugin_id": plugin_id,
        })
    return result


def _is_in_window(current_time, start, end):
    if start <= end:
        return start <= current_time < end
    return current_time >= start or current_time < end


@user_bp.route('/api/user/mode/select', methods=['POST'])
def select_mode():
    data = request.get_json()
    mode_name = data.get("mode_name") if data else None
    if not mode_name:
        return jsonify({"error": "mode_name is required"}), 400

    refresh_task = current_app.config.get('REFRESH_TASK')
    if not refresh_task:
        return jsonify({"error": "Refresh task not available"}), 500

    scheduler = refresh_task.scheduler
    if not scheduler or not scheduler.force_mode(mode_name):
        return jsonify({"error": f"Mode '{mode_name}' not found"}), 404

    refresh_task.signal_config_change()
    return jsonify({"success": True, "message": f"Switched to {mode_name}"})


@user_bp.route('/api/user/mode/display/<mode_name>', methods=['POST'])
def display_mode_now(mode_name):
    """Generate and display a specific mode's content immediately."""
    device_config = current_app.config['DEVICE_CONFIG']
    display_manager = current_app.config['DISPLAY_MANAGER']

    scheduler_cfg = device_config.get_config("scheduler", default={})
    mode = None
    for m in scheduler_cfg.get("modes", []):
        if m.get("name") == mode_name:
            mode = m
            break

    if not mode:
        return jsonify({"error": f"Mode '{mode_name}' not found"}), 404

    try:
        plugin_id = mode.get("plugin_id")
        if plugin_id:
            from plugins.plugin_registry import get_plugin_instance
            plugin_config = device_config.get_plugin(plugin_id)
            if plugin_config:
                plugin = get_plugin_instance(plugin_config)
                image = plugin.generate_image({}, device_config)
            else:
                image = Image.new('RGB', device_config.get_resolution(), 'white')
            display_manager.display_image(image)
            return jsonify({"success": True, "message": f"Displayed {plugin_id}"})

        interstitial_pool = mode.get("interstitial_pool", [])
        if interstitial_pool:
            from refresh_task import PhotoRefresh
            tz_str = device_config.get_config("timezone", default="UTC")
            current_dt = datetime.now(pytz.timezone(tz_str))
            action = PhotoRefresh()
            image = action.execute(None, device_config, current_dt)
            display_manager.display_image(image)
            return jsonify({"success": True, "message": "Displayed photo"})

        return jsonify({"error": "Mode has no content"}), 400
    except Exception as e:
        logger.exception("Failed to display mode '%s'", mode_name)
        return jsonify({"error": str(e)}), 500


@user_bp.route('/api/user/photos', methods=['GET'])
def list_photos():
    _ensure_photo_dir()
    exts = ('.jpg', '.jpeg', '.png', '.avif', '.webp', '.bmp', '.tiff', '.heif', '.heic')
    photos = []
    for f in sorted(os.listdir(PHOTO_DIR), reverse=True):
        if f.lower().endswith(exts) and not f.startswith('.'):
            photos.append({
                "filename": f,
                "url": f"/static/images/user_photos/{f}",
                "size": os.path.getsize(os.path.join(PHOTO_DIR, f)),
            })
    return jsonify(photos)


@user_bp.route('/api/user/photos/upload', methods=['POST'])
def upload_photos():
    _ensure_photo_dir()
    if 'photos' not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist('photos')
    uploaded = []
    errors = []

    for f in files:
        if f and f.filename and _allowed_file(f.filename):
            filename = secure_filename(f.filename)
            if not filename:
                continue
            dest = os.path.join(PHOTO_DIR, filename)
            f.save(dest)
            uploaded.append(filename)
        else:
            errors.append(f.filename if f else "unknown")

    return jsonify({"uploaded": uploaded, "errors": errors})


@user_bp.route('/api/user/photos/<filename>', methods=['DELETE'])
def delete_photo(filename):
    _ensure_photo_dir()
    safe = secure_filename(filename)
    path = os.path.join(PHOTO_DIR, safe)
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    os.remove(path)
    return jsonify({"success": True, "message": f"Deleted {safe}"})
