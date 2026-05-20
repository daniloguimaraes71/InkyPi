import threading
import time
import random
import os
import logging
import psutil
import pytz
from datetime import datetime, timezone
from plugins.plugin_registry import get_plugin_instance
from utils.image_utils import compute_image_hash
from model import RefreshInfo, PlaylistManager
from scheduler import SchedulerEngine
from PIL import Image

logger = logging.getLogger(__name__)

class RefreshTask:
    """Handles the logic for refreshing the display using a background thread."""

    def __init__(self, device_config, display_manager):
        self.device_config = device_config
        self.display_manager = display_manager
        self.scheduler = SchedulerEngine(device_config)

        self.thread = None
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.running = False
        self.manual_update_request = ()

        self.refresh_event = threading.Event()
        self.refresh_event.set()
        self.refresh_result = {}
        self._scheduler_sleep_time = 60
        self._first_run = True

    def start(self):
        """Starts the background thread for refreshing the display."""
        if not self.thread or not self.thread.is_alive():
            logger.info("Starting refresh task")
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.running = True
            self.thread.start()

    def stop(self):
        """Stops the refresh task by notifying the background thread to exit."""
        with self.condition:
            self.running = False
            self.condition.notify_all()  # Wake the thread to let it exit
        if self.thread:
            logger.info("Stopping refresh task")
            self.thread.join()

    def _run(self):
        """Background task that manages the periodic refresh of the display.

        This function runs in a loop, sleeping for a configured duration (`plugin_cycle_interval_seconds`) or until
        manually triggered via `manual_update()`. Determines the next plugin to refresh based on active playlists and
        updates the display accordingly.

        Workflow:
        1. Waits for the configured sleep duration or until notified of a manual update.
        2. Checks if a manual update has been requested:
        - If so, refreshes the specified plugin immediately.
        3. Otherwise, determines the next plugin to refresh based on the active playlist and generates an image.
        4. Compares the image hash with the last displayed image hash.
        - If the image has changed, updates the display.
        - If the image is the same, skips the refresh.
        5. Updates the refresh metadata in the device configuration.
        6. Repeats the process until `stop()` is called.

        Handles any exceptions that occur during the refresh process and ensures the refresh event is set 
        to indicate completion.

        Exceptions:
        - Captures and logs any unexpected errors during execution to prevent the thread from exiting.
        """
        while True:
            try:
                with self.condition:
                    # Determine sleep time: scheduler or legacy
                    if self.scheduler.is_enabled():
                        sleep_time = self._scheduler_sleep_time
                    else:
                        sleep_time = self.device_config.get_config("plugin_cycle_interval_seconds", default=60*60)
                    self._scheduler_sleep_time = sleep_time

                    # Wait for sleep_time or until notified
                    self.condition.wait(timeout=sleep_time)
                    self.refresh_result = {}
                    self.refresh_event.clear()

                    # Exit if `stop()` is called
                    if not self.running:
                        break

                    playlist_manager = self.device_config.get_playlist_manager()
                    latest_refresh = self.device_config.get_refresh_info()
                    current_dt = self._get_current_datetime()

                    refresh_action = None
                    if self.manual_update_request:
                        # handle immediate update request
                        logger.info("Manual update requested")
                        refresh_action = self.manual_update_request
                        self.manual_update_request = ()
                    else:
                        # Check persistent user display mode override
                        user_mode = self.device_config.get_config("user_display_mode", default="scheduled")
                        if user_mode == "clock_only":
                            logger.info("User mode: clock_only")
                            refresh_action = ManualRefresh("clock", {})
                        elif user_mode == "photos_only":
                            logger.info("User mode: photos_only")
                            refresh_action = PhotoRefresh(user_photos_only=True)
                            self._scheduler_sleep_time = self.device_config.get_config("photos_interval_seconds", default=300)
                        elif user_mode in ("calendar_month", "calendar_week", "calendar_day"):
                            logger.info("User mode: %s", user_mode)
                            view_map = {
                                "calendar_month": "dayGridMonth",
                                "calendar_week": "timeGridWeek",
                                "calendar_day": "timeGridDay",
                            }
                            refresh_action = ManualRefresh("calendar", {"viewMode": view_map[user_mode]})
                            self._scheduler_sleep_time = 3600
                        else:
                            if self.device_config.get_config("log_system_stats"):
                                self.log_system_stats()

                            if self.scheduler.is_enabled():
                                # Check for interrupts (calendar events, weather alerts)
                                tz_str = self.device_config.get_config("timezone", default="UTC")
                                tz = pytz.timezone(tz_str)
                                self.scheduler.check_calendar_interrupts(current_dt, tz)
                                self.scheduler.check_weather_alerts(current_dt, self.device_config)

                                # Use scheduler engine
                                logger.info(f"Scheduler check. | current_time: {current_dt.strftime('%Y-%m-%d %H:%M:%S')} | mode: {self.scheduler._current_mode}")
                                action, next_sleep = self.scheduler.next_action(current_dt, playlist_manager, latest_refresh)
                                self._scheduler_sleep_time = next_sleep
                                refresh_action = action
                            else:
                                # Legacy playlist-based refresh
                                logger.info(f"Running interval refresh check. | current_time: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                playlist, plugin_instance = self._determine_next_plugin(playlist_manager, latest_refresh, current_dt)
                                if plugin_instance:
                                    refresh_action = PlaylistRefresh(playlist, plugin_instance)

                    if refresh_action:
                        if isinstance(refresh_action, PhotoRefresh):
                            image = refresh_action.execute(None, self.device_config, current_dt)
                            image_settings = []
                        else:
                            plugin_config = self.device_config.get_plugin(refresh_action.get_plugin_id())
                            if plugin_config is None:
                                logger.error(f"Plugin config not found for '{refresh_action.get_plugin_id()}'.")
                                continue
                            plugin = get_plugin_instance(plugin_config)
                            image = refresh_action.execute(plugin, self.device_config, current_dt)
                            image_settings = plugin.config.get("image_settings", [])
                        image_hash = compute_image_hash(image)

                        refresh_info = refresh_action.get_refresh_info()
                        refresh_info.update({"refresh_time": current_dt.isoformat(), "image_hash": image_hash})
                        if self._first_run or image_hash != latest_refresh.image_hash:
                            self._first_run = False
                            logger.info(f"Updating display. | refresh_info: {refresh_info}")
                            self.display_manager.display_image(image, image_settings=image_settings)
                        else:
                            logger.info(f"Image already displayed, skipping refresh. | refresh_info: {refresh_info}")

                        # update latest refresh data in the device config
                        self.device_config.refresh_info = RefreshInfo(**refresh_info)
                        self.device_config.write_config()

            except Exception as e:
                logger.exception('Exception during refresh')
                self.refresh_result["exception"] = e  # Capture exception
            finally:
                self.refresh_event.set()

    def manual_update(self, refresh_action):
        """Manually triggers an update for the specified plugin id and plugin settings by notifying the background process."""
        if self.running:
            with self.condition:
                self.manual_update_request = refresh_action
                self.refresh_result = {}
                self.refresh_event.clear()

                self.condition.notify_all()  # Wake the thread to process manual update

            self.refresh_event.wait()
            if self.refresh_result.get("exception"):
                raise self.refresh_result.get("exception")
        else:
            logger.warning("Background refresh task is not running, unable to do a manual update")

    def signal_config_change(self):
        """Notify the background thread that config has changed (e.g., interval updated)."""
        if self.running:
            with self.condition:
                self.condition.notify_all()

    def _get_current_datetime(self):
        """Retrieves the current datetime based on the device's configured timezone."""
        tz_str = self.device_config.get_config("timezone", default="UTC")
        return datetime.now(pytz.timezone(tz_str))

    def _determine_next_plugin(self, playlist_manager, latest_refresh_info, current_dt):
        """Determines the next plugin to refresh based on the active playlist, plugin cycle interval, and current time."""
        playlist = playlist_manager.determine_active_playlist(current_dt)
        if not playlist:
            playlist_manager.active_playlist = None
            logger.info(f"No active playlist determined.")
            return None, None

        playlist_manager.active_playlist = playlist.name
        if not playlist.plugins:
            logger.info(f"Active playlist '{playlist.name}' has no plugins.")
            return None, None

        latest_refresh_dt = latest_refresh_info.get_refresh_datetime()
        plugin_cycle_interval = self.device_config.get_config("plugin_cycle_interval_seconds", default=3600)
        should_refresh = PlaylistManager.should_refresh(latest_refresh_dt, plugin_cycle_interval, current_dt)

        if not should_refresh:
            latest_refresh_str = latest_refresh_dt.strftime('%Y-%m-%d %H:%M:%S') if latest_refresh_dt else "None"
            logger.info(f"Not time to update display. | latest_update: {latest_refresh_str} | plugin_cycle_interval: {plugin_cycle_interval}")
            return None, None

        plugin = playlist.get_next_plugin()
        logger.info(f"Determined next plugin. | active_playlist: {playlist.name} | plugin_instance: {plugin.name}")

        return playlist, plugin
    
    def log_system_stats(self):
        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_avg_1_5_15': os.getloadavg(),
            'swap_percent': psutil.swap_memory().percent,
            'net_io': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv
            }
        }

        logger.info(f"System Stats: {metrics}")

class RefreshAction:
    """Base class for a refresh action. Subclasses should override the methods below."""
    
    def refresh(self, plugin, device_config, current_dt):
        """Perform a refresh operation and return the updated image."""
        raise NotImplementedError("Subclasses must implement the refresh method.")
    
    def get_refresh_info(self):
        """Return refresh metadata as a dictionary."""
        raise NotImplementedError("Subclasses must implement the get_refresh_info method.")
    
    def get_plugin_id(self):
        """Return the plugin ID associated with this refresh."""
        raise NotImplementedError("Subclasses must implement the get_plugin_id method.")

class ManualRefresh(RefreshAction):
    """Performs a manual refresh based on a plugin's ID and its associated settings.
    
    Attributes:
        plugin_id (str): The ID of the plugin to refresh.
        plugin_settings (dict): The settings for the manual refresh.
    """

    def __init__(self, plugin_id: str, plugin_settings: dict):
        self.plugin_id = plugin_id
        self.plugin_settings = plugin_settings

    def execute(self, plugin, device_config, current_dt: datetime):
        """Performs a manual refresh using the stored plugin ID and settings."""
        return plugin.generate_image(self.plugin_settings, device_config)

    def get_refresh_info(self):
        """Return refresh metadata as a dictionary."""
        return {"refresh_type": "Manual Update", "plugin_id": self.plugin_id}

    def get_plugin_id(self):
        """Return the plugin ID associated with this refresh."""
        return self.plugin_id

class PlaylistRefresh(RefreshAction):
    """Performs a refresh using a plugin instance within a playlist context.

    Attributes:
        playlist: The playlist object associated with the refresh.
        plugin_instance: The plugin instance to refresh.
    """

    def __init__(self, playlist, plugin_instance, force=False):
        self.playlist = playlist
        self.plugin_instance = plugin_instance
        self.force = force

    def get_refresh_info(self):
        """Return refresh metadata as a dictionary."""
        return {
            "refresh_type": "Playlist",
            "playlist": self.playlist.name,
            "plugin_id": self.plugin_instance.plugin_id,
            "plugin_instance": self.plugin_instance.name
        }

    def get_plugin_id(self):
        """Return the plugin ID associated with this refresh."""
        return self.plugin_instance.plugin_id

    def execute(self, plugin, device_config, current_dt: datetime):
        """Performs a refresh for the specified plugin instance within its playlist context."""
        # Determine the file path for the plugin's image
        plugin_image_path = os.path.join(device_config.plugin_image_dir, self.plugin_instance.get_image_path())

        # Check if a refresh is needed based on the plugin instance's criteria
        if self.plugin_instance.should_refresh(current_dt) or self.force:
            logger.info(f"Refreshing plugin instance. | plugin_instance: '{self.plugin_instance.name}'") 
            # Generate a new image
            image = plugin.generate_image(self.plugin_instance.settings, device_config)
            image.save(plugin_image_path)
            self.plugin_instance.latest_refresh_time = current_dt.isoformat()
        else:
            logger.info(f"Not time to refresh plugin instance, using latest image. | plugin_instance: {self.plugin_instance.name}.")
            # Load the existing image from disk
            with Image.open(plugin_image_path) as img:
                image = img.copy()

        return image


class PhotoRefresh(RefreshAction):
    """Refresh action that picks and displays a random photo.

    By default scans standard photo directories. When `user_photos_only=True`,
    only picks from user-uploaded photos (no local folder fallback).
    """

    PHOTO_DIRS = [
        os.path.expanduser("~/Pictures"),
        os.path.expanduser("~/Photos"),
        os.path.expanduser("~/写真"),
        "/media",
        "/mnt",
    ]

    @classmethod
    def get_user_photo_dir(cls):
        return os.path.join(os.path.dirname(__file__), "static", "images", "user_photos")

    def __init__(self, user_photos_only=False):
        self.plugin_id = "photo"
        self.user_photos_only = user_photos_only

    @staticmethod
    def find_user_photo():
        """Pick a random photo from user_uploads only."""
        exts = ('.jpg', '.jpeg', '.png', '.avif', '.webp', '.bmp', '.tiff', '.heif', '.heic')
        user_dir = PhotoRefresh.get_user_photo_dir()
        if not os.path.isdir(user_dir):
            return None
        candidates = []
        for f in os.listdir(user_dir):
            if f.lower().endswith(exts) and not f.startswith('.'):
                candidates.append(os.path.join(user_dir, f))
        return random.choice(candidates) if candidates else None

    @staticmethod
    def find_random_photo():
        """Pick a random photo from user_uploads; fall back to common directories if empty."""
        exts = ('.jpg', '.jpeg', '.png', '.avif', '.webp', '.bmp', '.tiff', '.heif', '.heic')
        candidates = []
        user_dir = PhotoRefresh.get_user_photo_dir()
        if os.path.isdir(user_dir):
            for f in os.listdir(user_dir):
                if f.lower().endswith(exts) and not f.startswith('.'):
                    candidates.append(os.path.join(user_dir, f))
        if candidates:
            return random.choice(candidates)
        for d in PhotoRefresh.PHOTO_DIRS:
            if os.path.isdir(d):
                for root, _, files in os.walk(d):
                    for f in files:
                        if f.lower().endswith(exts) and not f.startswith('.'):
                            candidates.append(os.path.join(root, f))
        if not candidates:
            return None
        return random.choice(candidates)

    def execute(self, plugin, device_config, current_dt):
        """Pick a random photo, display with blur background, or fall back to clock."""
        if self.user_photos_only:
            path = self.find_user_photo()
        else:
            path = self.find_random_photo()
        if path:
            img = Image.open(path).convert("RGB")
            target = list(device_config.get_resolution())
            if device_config.get_config("orientation") == "vertical":
                target = target[::-1]

            # Create blurred background
            small = img.resize((64, 48), Image.Resampling.LANCZOS)
            bg = small.resize(target, Image.Resampling.LANCZOS)

            # Fit image preserving aspect ratio, centered on background
            img_ratio = img.width / img.height
            target_ratio = target[0] / target[1]
            if img_ratio > target_ratio:
                new_w = target[0]
                new_h = int(new_w / img_ratio)
            else:
                new_h = target[1]
                new_w = int(new_h * img_ratio)
            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            x = (target[0] - new_w) // 2
            y = (target[1] - new_h) // 2
            bg.paste(resized, (x, y))
            return bg

        # Fallback: clock
        from plugins.plugin_registry import get_plugin_instance
        plugin_config = device_config.get_plugin("clock")
        if plugin_config:
            clock = get_plugin_instance(plugin_config)
            return clock.generate_image({}, device_config)
        # Ultimate fallback: blank
        w, h = device_config.get_resolution()
        return Image.new('RGB', (w, h), 'white')
        # Fallback: clock
        from plugins.plugin_registry import get_plugin_instance
        plugin_config = device_config.get_plugin("clock")
        if plugin_config:
            clock = get_plugin_instance(plugin_config)
            return clock.generate_image({}, device_config)
        # Ultimate fallback: blank
        w, h = device_config.get_resolution()
        return Image.new('RGB', (w, h), 'white')

    def get_refresh_info(self):
        return {"refresh_type": "Photo", "plugin_id": self.plugin_id}

    def get_plugin_id(self):
        return self.plugin_id


class CalendarInterrupt(RefreshAction):
    """Interrupt action for upcoming calendar events.

    Generates an elegant notification card in Japanese style.
    """

    def __init__(self, event_data):
        self.event_data = event_data
        self.plugin_id = "calendar_interrupt"

    def execute(self, plugin, device_config, current_dt: datetime):
        """Generate a calendar notification card."""
        from PIL import Image, ImageDraw
        from utils.app_utils import get_font
        from utils.design_variants import get_variant

        w, h = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            w, h = h, w

        v = get_variant(device_config.get_config("design_style"), None)
        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg'])
        draw = ImageDraw.Draw(img)

        font_label = get_font(v.body_font, int(w * 0.028))
        font_title = get_font(v.heading_font, int(w * 0.055))
        font_time = get_font(v.body_font, int(w * 0.028))
        font_date = get_font(v.body_font, int(w * 0.018))

        title = self.event_data.get("title", "予定")
        minutes = self.event_data.get("minutes_until", 0)

        if minutes <= 0:
            time_str = "まもなく開始"
        elif minutes == 1:
            time_str = "1分後"
        else:
            time_str = f"{minutes}分後"

        cx = w // 2

        label = "次の予定"
        bbox = draw.textbbox((0, 0), label, font=font_label)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, int(h * 0.28 * sm)), label, font=font_label, fill=C['accent'])

        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        if tw > w * 0.8:
            font_title = get_font(v.heading_font, int(w * 0.04))
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, int(h * 0.36 * sm)), title, font=font_title, fill=C['text_primary'])

        dy = int(h * 0.47 * sm)
        dw = int(w * 0.12)
        draw.line([(cx - dw, dy), (cx + dw, dy)], fill=C['divider'], width=v.divider_width * 2)

        bbox = draw.textbbox((0, 0), time_str, font=font_time)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, int(h * 0.52 * sm)), time_str, font=font_time, fill=C['text_secondary'])

        date_str = current_dt.strftime('%m月%d日')
        bbox = draw.textbbox((0, 0), date_str, font=font_date)
        draw.text((w - int(w * 0.05) - (bbox[2] - bbox[0]), h - int(h * 0.06 * sm)), date_str, font=font_date, fill=C['text_light'])

        return img

    def get_refresh_info(self):
        return {"refresh_type": "Calendar Interrupt", "plugin_id": self.plugin_id}

    def get_plugin_id(self):
        return self.plugin_id


class WeatherAlertInterrupt(RefreshAction):
    """Interrupt action for weather alerts."""

    def __init__(self, alert_data):
        self.alert_data = alert_data
        self.plugin_id = "weather_alert_interrupt"

    def execute(self, plugin, device_config, current_dt: datetime):
        """Generate a weather alert card."""
        from PIL import Image, ImageDraw
        from utils.app_utils import get_font
        from utils.design_variants import get_variant

        w, h = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            w, h = h, w

        v = get_variant(device_config.get_config("design_style"), None)
        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg_alt'])
        draw = ImageDraw.Draw(img)

        font_label = get_font(v.body_font, int(w * 0.028))
        font_title = get_font(v.heading_font, int(w * 0.05))
        font_desc = get_font(v.body_font, int(w * 0.024))
        font_date = get_font(v.body_font, int(w * 0.018))

        event = self.alert_data.get("event", "気象警報")
        description = self.alert_data.get("description", "")[:120]

        cx = w // 2

        label = "気象警報"
        bbox = draw.textbbox((0, 0), label, font=font_label)
        draw.text((cx - (bbox[2] - bbox[0]) // 2, int(h * 0.26 * sm)), label, font=font_label, fill=C['accent_alt'])

        bbox = draw.textbbox((0, 0), event, font=font_title)
        tw = bbox[2] - bbox[0]
        if tw > w * 0.8:
            font_title = get_font(v.heading_font, int(w * 0.038))
            bbox = draw.textbbox((0, 0), event, font=font_title)
            tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, int(h * 0.35 * sm)), event, font=font_title, fill=C['text_primary'])

        dy = int(h * 0.46 * sm)
        dw = int(w * 0.12)
        draw.line([(cx - dw, dy), (cx + dw, dy)], fill=C['divider'], width=v.divider_width * 2)

        if description:
            desc_lines = []
            words = description.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=font_desc)
                if bbox[2] - bbox[0] > w * 0.8:
                    desc_lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            desc_lines.append(current_line)

            line_y = int(h * 0.50 * sm)
            for line in desc_lines:
                bbox = draw.textbbox((0, 0), line, font=font_desc)
                draw.text((cx - (bbox[2] - bbox[0]) // 2, line_y), line, font=font_desc, fill=C['text_secondary'])
                line_y += int(h * 0.045 * sm)

        date_str = current_dt.strftime('%m月%d日')
        bbox = draw.textbbox((0, 0), date_str, font=font_date)
        draw.text((w - int(w * 0.05) - (bbox[2] - bbox[0]), h - int(h * 0.06 * sm)), date_str, font=font_date, fill=C['text_light'])

        return img

    def get_refresh_info(self):
        return {"refresh_type": "Weather Alert", "plugin_id": self.plugin_id}

    def get_plugin_id(self):
        return self.plugin_id