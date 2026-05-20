import logging
import random
import requests
from datetime import datetime, timedelta
from model import PlaylistManager

logger = logging.getLogger(__name__)

DEFAULT_PHOTO_DWELL = 300            # 5 minutes per photo
DEFAULT_CARD_DWELL = 300             # 5 minutes per info card
DEFAULT_INTERSTITIAL_INTERVAL = 1800  # 30 min between random cards
DEFAULT_INTERSTITIAL_DWELL = 120      # 2 min showing random card
DEFAULT_INTERRUPT_CHECK = 300         # Check interrupts every 5 min

ALL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class SchedulerEngine:
    """Mode-based scheduler that rotates between photo frame and info cards.

    Reads a 'scheduler' config block from device.json.
    Modes support three patterns:
      - plugin_id: single fixed card shown for dwell_seconds
      - interstitial_pool: photos with occasional random cards
      - playlists: multi-plugin rotation
    Plus day-of-week targeting on every mode.
    """

    def __init__(self, config):
        self.config = config
        self.scheduler_config = config.get_config("scheduler", default={})
        self.enabled = self.scheduler_config.get("enabled", False)
        self.modes = self.scheduler_config.get("modes", [])
        self._current_mode = None
        self._interrupt_queue = []
        self._last_interrupt_check = None
        self._last_interstitial_time = None
        self._mode_switch_time = None
        self._forced_mode_name = None

    def is_enabled(self):
        return self.enabled and len(self.modes) > 0

    # ------------------------------------------------------------------
    # Active mode detection
    # ------------------------------------------------------------------

    def get_active_mode(self, current_dt):
        """Return the mode whose time window and day-of-week match now."""
        current_time = current_dt.strftime("%H:%M")
        day_key = current_dt.strftime("%a").lower()

        active = []
        for mode in self.modes:
            if day_key not in mode.get("days", ALL_DAYS):
                continue
            if self._is_in_window(current_time, mode.get("start_time", "00:00"), mode.get("end_time", "24:00")):
                active.append(mode)

        if not active:
            return None
        active.sort(key=lambda m: self._window_minutes(m))
        return active[0]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def force_mode(self, mode_name):
        """Force the scheduler to show a specific mode for one cycle."""
        for mode in self.modes:
            if mode.get("name") == mode_name:
                self._forced_mode_name = mode_name
                self._forced_mode_until = None
                self._current_mode = mode_name
                self._last_interstitial_time = None
                logger.info("Force mode: %s", mode_name)
                return True
        logger.warning("Force mode: mode '%s' not found", mode_name)
        return False

    def next_action(self, current_dt, playlist_manager, latest_refresh_info):
        """Determine the next display action. Returns (action | None, sleep_seconds)."""
        if self._interrupt_queue:
            return self._interrupt_queue.pop(0), 0

        if not self.is_enabled():
            return None, self._get_default_sleep()

        # Check forced mode
        if self._forced_mode_name:
            for mode in self.modes:
                if mode.get("name") == self._forced_mode_name:
                    self._forced_mode_name = None
                    return self._resolve_mode_action(mode, current_dt, playlist_manager, latest_refresh_info)
            self._forced_mode_name = None

        active_mode = self.get_active_mode(current_dt)
        if not active_mode:
            return None, self._fallback_sleep()

        mode_switched = active_mode.get("name") != self._current_mode
        if mode_switched:
            logger.info("Switched to mode: %s", active_mode.get("name"))
            self._current_mode = active_mode.get("name")
            self._last_interstitial_time = None
            self._mode_switch_time = current_dt

        interstitial_pool = active_mode.get("interstitial_pool", [])
        if interstitial_pool:
            return self._handle_interstitial_mode(active_mode, current_dt, latest_refresh_info)

        plugin_id = active_mode.get("plugin_id")
        if plugin_id:
            return self._handle_plugin_mode(active_mode, current_dt, latest_refresh_info)

        return self._handle_playlist_mode(active_mode, current_dt, playlist_manager, latest_refresh_info)

    # ------------------------------------------------------------------
    # Mode handlers
    # ------------------------------------------------------------------

    def _handle_plugin_mode(self, mode, current_dt, latest_refresh_info):
        """Show a single fixed plugin for its entire dwell duration."""
        dwell = mode.get("dwell_seconds", DEFAULT_CARD_DWELL)
        plugin_id = mode.get("plugin_id")

        from refresh_task import ManualRefresh
        logger.info("Fixed plugin mode: showing %s", plugin_id)
        return ManualRefresh(plugin_id, {}), dwell

    def _handle_interstitial_mode(self, mode, current_dt, latest_refresh_info):
        """Photos as resting state with occasional random interstitial cards."""
        dwell = mode.get("dwell_seconds", DEFAULT_PHOTO_DWELL)
        interstitial_interval = mode.get("interstitial_interval_seconds", DEFAULT_INTERSTITIAL_INTERVAL)
        interstitial_dwell = mode.get("interstitial_dwell_seconds", DEFAULT_INTERSTITIAL_DWELL)
        interstitial_pool = mode.get("interstitial_pool", [])

        if self._last_interstitial_time:
            time_since = (current_dt - self._last_interstitial_time).total_seconds()
        else:
            # Show a photo immediately on mode switch; set timer so next check acts properly
            self._last_interstitial_time = current_dt
            from refresh_task import PhotoRefresh
            logger.debug("Interstitial mode: first photo")
            return PhotoRefresh(), dwell

        # Check for interstitial card
        if time_since >= interstitial_interval and interstitial_pool:
            plugin_id = random.choice(interstitial_pool)
            self._last_interstitial_time = current_dt
            from refresh_task import ManualRefresh
            logger.info("Interstitial: showing %s", plugin_id)
            return ManualRefresh(plugin_id, {}), interstitial_dwell

        # Next photo
        from refresh_task import PhotoRefresh
        logger.debug("Interstitial mode: next photo")
        return PhotoRefresh(), dwell

    def _handle_playlist_mode(self, mode, current_dt, playlist_manager, latest_refresh_info):
        """Rotate through plugins in playlists."""
        dwell = mode.get("dwell_seconds", DEFAULT_CARD_DWELL)

        latest_dt = latest_refresh_info.get_refresh_datetime()
        if latest_dt:
            elapsed = (current_dt - latest_dt).total_seconds()
            if elapsed < dwell:
                return None, min(dwell - elapsed, 60)

        mode_playlists = mode.get("playlists", [])
        if not mode_playlists:
            return None, dwell

        plugin_instance, playlist_name = self._pick_from_playlists(mode_playlists, mode, playlist_manager)

        if not plugin_instance:
            return None, dwell

        from refresh_task import PlaylistRefresh
        playlist = playlist_manager.get_playlist(playlist_name) if playlist_manager else None
        action = PlaylistRefresh(playlist, plugin_instance)

        rotate = mode.get("rotate", False)
        sleep = mode.get("rotate_interval_seconds", DEFAULT_CARD_DWELL) if rotate else dwell
        return action, sleep

    # ------------------------------------------------------------------
    # Interrupt management
    # ------------------------------------------------------------------

    def queue_interrupt(self, refresh_action):
        """Queue a high-priority interrupt (calendar event, weather alert)."""
        self._interrupt_queue.append(refresh_action)
        logger.info("Interrupt queued: %s", refresh_action)

    def check_calendar_interrupts(self, current_dt, tz):
        """Check for upcoming calendar events and queue interrupts."""
        cal_cfg = self.scheduler_config.get("interrupts", {}).get("calendar", {})
        if not cal_cfg.get("enabled", False):
            return

        check_interval = cal_cfg.get("check_interval_seconds", DEFAULT_INTERRUPT_CHECK)
        if self._last_interrupt_check:
            if (current_dt - self._last_interrupt_check).total_seconds() < check_interval:
                return
        self._last_interrupt_check = current_dt

        for url in cal_cfg.get("urls", []):
            try:
                events = self._fetch_upcoming_events(url, current_dt, tz, cal_cfg.get("threshold_minutes", 15))
                for ev in events:
                    from refresh_task import CalendarInterrupt
                    self.queue_interrupt(CalendarInterrupt(ev))
            except Exception as e:
                logger.warning("Calendar interrupt check failed for %s: %s", url, e)

    def check_weather_alerts(self, current_dt, device_config):
        """Check for weather alerts and queue interrupts."""
        wx_cfg = self.scheduler_config.get("interrupts", {}).get("weather_alerts", {})
        if not wx_cfg.get("enabled", False):
            return

        try:
            api_key = device_config.load_env_key("OPEN_WEATHER_MAP_SECRET")
            lat = device_config.get_config("latitude")
            lon = device_config.get_config("longitude")
            if not all([api_key, lat, lon]):
                return

            resp = requests.get(
                f"https://api.openweathermap.org/data/2.5/alerts?lat={lat}&lon={lon}&appid={api_key}",
                timeout=10,
            )
            if resp.status_code == 200:
                alerts = resp.json().get("alerts", [])
                for alert in alerts[:1]:
                    from refresh_task import WeatherAlertInterrupt
                    self.queue_interrupt(WeatherAlertInterrupt(alert))
        except Exception as e:
            logger.warning("Weather alert check failed: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_from_playlists(self, playlist_names, mode, playlist_manager=None):
        for pl_name in playlist_names:
            pm = playlist_manager or self.config.get_playlist_manager()
            playlist = pm.get_playlist(pl_name) if pm else None
            if not playlist or not playlist.plugins:
                continue
            if mode.get("random", False):
                return random.choice(playlist.plugins), pl_name
            if playlist.current_plugin_index is not None:
                idx = playlist.current_plugin_index % len(playlist.plugins)
            else:
                idx = 0
                playlist.current_plugin_index = 0
            return playlist.plugins[idx], pl_name
        return None, None

    def _fetch_upcoming_events(self, calendar_url, current_dt, tz, threshold_minutes):
        import icalendar
        import recurring_ical_events

        if calendar_url.startswith("webcal://"):
            calendar_url = calendar_url.replace("webcal://", "https://")

        resp = requests.get(calendar_url, timeout=15)
        resp.raise_for_status()
        cal = icalendar.Calendar.from_ical(resp.text)

        end = current_dt + timedelta(minutes=threshold_minutes)
        events = recurring_ical_events.of(cal).between(current_dt, end)

        upcoming = []
        for ev in events:
            dtstart = ev.decoded("dtstart")
            if isinstance(dtstart, datetime):
                dtstart = dtstart.astimezone(tz)
            upcoming.append({
                "title": str(ev.get("summary", "")),
                "start": dtstart,
                "minutes_until": int((dtstart - current_dt).total_seconds() / 60),
            })
        return upcoming

    def _is_in_window(self, current_time, start, end):
        if start <= end:
            return start <= current_time < end
        return current_time >= start or current_time < end

    def _window_minutes(self, mode):
        try:
            s_h, s_m = map(int, mode.get("start_time", "00:00").split(":"))
            e_h, e_m = map(int, mode.get("end_time", "24:00").split(":"))
            total = e_h * 60 + e_m - (s_h * 60 + s_m)
            return total if total > 0 else total + 1440
        except (ValueError, AttributeError):
            return 1440

    def _fallback_sleep(self):
        return self.config.get_config("plugin_cycle_interval_seconds", default=3600)

    def _get_default_sleep(self):
        return self.config.get_config("plugin_cycle_interval_seconds", default=3600)

    # ------------------------------------------------------------------
    # Status (for web UI)
    # ------------------------------------------------------------------

    def _resolve_mode_action(self, mode, current_dt, playlist_manager, latest_refresh_info):
        """Resolve a mode dict into a refresh action without switching mode tracking."""
        interstitial_pool = mode.get("interstitial_pool", [])
        if interstitial_pool:
            return self._handle_interstitial_mode(mode, current_dt, latest_refresh_info)
        plugin_id = mode.get("plugin_id")
        if plugin_id:
            return self._handle_plugin_mode(mode, current_dt, latest_refresh_info)
        return self._handle_playlist_mode(mode, current_dt, playlist_manager, latest_refresh_info)

    def get_status(self):
        return {
            "enabled": self.is_enabled(),
            "current_mode": self._current_mode,
            "forced_mode": self._forced_mode_name,
            "modes_count": len(self.modes),
            "interrupts_queued": len(self._interrupt_queue),
        }
