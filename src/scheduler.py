import logging
import requests
from datetime import datetime, timedelta
from model import PlaylistManager

logger = logging.getLogger(__name__)

DEFAULT_PHOTO_DWELL = 1800    # 30 minutes for photo frame
DEFAULT_CARD_DWELL = 300      # 5 minutes for info cards
DEFAULT_CARD_ROTATE = 60      # 1 minute between card rotations
DEFAULT_INTERRUPT_CHECK = 300 # Check for interrupts every 5 minutes


class SchedulerEngine:
    """Mode-based scheduler that rotates between photo frame and info cards.

    Reads a 'scheduler' config block from device.json:
    {
        "scheduler": {
            "enabled": true,
            "modes": [
                {"name": "...", "start_time": "HH:MM", "end_time": "HH:MM",
                 "playlists": ["..."], "dwell_seconds": 1800, "rotate": false}
            ]
        }
    }

    Falls back to the legacy PlaylistManager when scheduler is disabled.
    """

    def __init__(self, config):
        self.config = config
        self.scheduler_config = config.get_config("scheduler", default={})
        self.enabled = self.scheduler_config.get("enabled", False)
        self.modes = self.scheduler_config.get("modes", [])
        self._current_mode = None
        self._current_playlist_name = None
        self._interrupt_queue = []
        self._last_interrupt_check = None

    def is_enabled(self):
        return self.enabled and len(self.modes) > 0

    def get_active_mode(self, current_dt):
        """Determine which scheduler mode is active based on current time."""
        current_time = current_dt.strftime("%H:%M")

        active = []
        for mode in self.modes:
            start = mode.get("start_time", "00:00")
            end = mode.get("end_time", "24:00")
            if self._is_in_window(current_time, start, end):
                active.append(mode)

        if not active:
            return None

        # Narrowest window wins (highest priority)
        active.sort(key=lambda m: self._window_minutes(m))
        return active[0]

    def next_action(self, current_dt, playlist_manager, latest_refresh_info):
        """Determine the next refresh action. Returns (action, sleep_seconds) or (None, sleep_seconds).

        This is the main entry point called by RefreshTask.
        """
        # Check for interrupts first (calendar, weather alerts)
        if self._interrupt_queue:
            interrupt = self._interrupt_queue.pop(0)
            logger.info(f"Processing interrupt: {interrupt}")
            return interrupt, 0

        if not self.is_enabled():
            return None, self._get_default_sleep()

        active_mode = self.get_active_mode(current_dt)
        if not active_mode:
            logger.debug("No active scheduler mode")
            return self._fallback_sleep(current_dt)

        # Check if we need to switch modes
        if active_mode.get("name") != self._current_mode:
            logger.info(f"Switching to mode: {active_mode.get('name')}")
            self._current_mode = active_mode.get("name")
            self._current_playlist_name = None

        # Get dwell time for this mode
        dwell_seconds = active_mode.get("dwell_seconds", DEFAULT_PHOTO_DWELL)

        # Check if enough time has passed since last refresh
        latest_dt = latest_refresh_info.get_refresh_datetime()
        if latest_dt:
            elapsed = (current_dt - latest_dt).total_seconds()
            if elapsed < dwell_seconds:
                remaining = dwell_seconds - elapsed
                logger.debug(f"Mode '{self._current_mode}' dwell not elapsed, {remaining:.0f}s remaining")
                return None, min(remaining, 60)

        # Get playlists for this mode
        mode_playlists = active_mode.get("playlists", [])
        if not mode_playlists:
            logger.warning(f"Mode '{self._current_mode}' has no playlists")
            return None, dwell_seconds

        # Find the next plugin from the mode's playlists
        plugin_instance, playlist_name = self._get_next_plugin(
            mode_playlists, playlist_manager, active_mode
        )

        if not plugin_instance:
            logger.info(f"No plugins found in mode '{self._current_mode}'")
            return None, dwell_seconds

        self._current_playlist_name = playlist_name

        # Create the refresh action
        from refresh_task import PlaylistRefresh
        playlist = playlist_manager.get_playlist(playlist_name)
        action = PlaylistRefresh(playlist, plugin_instance)

        # For rotating modes (info cards), use shorter sleep
        if active_mode.get("rotate", False):
            rotate_interval = active_mode.get("rotate_interval_seconds", DEFAULT_CARD_ROTATE)
            return action, rotate_interval

        return action, dwell_seconds

    def queue_interrupt(self, refresh_action):
        """Queue a high-priority interrupt (e.g., calendar event, weather alert)."""
        self._interrupt_queue.append(refresh_action)
        logger.info(f"Interrupt queued: {refresh_action}")

    def check_calendar_interrupts(self, current_dt, tz):
        """Check for upcoming calendar events and queue interrupts if needed.

        Called periodically by RefreshTask. Checks calendar URLs configured
        in scheduler.interrupts.calendar for events starting within the
        configured threshold (default 15 minutes).
        """
        interrupt_config = self.scheduler_config.get("interrupts", {})
        calendar_config = interrupt_config.get("calendar", {})

        if not calendar_config.get("enabled", False):
            return

        # Rate limit checks
        check_interval = calendar_config.get("check_interval_seconds", DEFAULT_INTERRUPT_CHECK)
        if self._last_interrupt_check:
            elapsed = (current_dt - self._last_interrupt_check).total_seconds()
            if elapsed < check_interval:
                return

        self._last_interrupt_check = current_dt

        calendar_urls = calendar_config.get("urls", [])
        threshold_minutes = calendar_config.get("threshold_minutes", 15)

        for url in calendar_urls:
            try:
                events = self._fetch_upcoming_events(url, current_dt, tz, threshold_minutes)
                for event in events:
                    # Create a calendar notification card action
                    from refresh_task import CalendarInterrupt
                    interrupt = CalendarInterrupt(event)
                    self.queue_interrupt(interrupt)
            except Exception as e:
                logger.warning(f"Failed to check calendar interrupts for {url}: {e}")

    def check_weather_alerts(self, current_dt, device_config):
        """Check for weather alerts and queue interrupts if needed."""
        interrupt_config = self.scheduler_config.get("interrupts", {})
        weather_config = interrupt_config.get("weather_alerts", {})

        if not weather_config.get("enabled", False):
            return

        try:
            api_key = device_config.load_env_key("OPEN_WEATHER_MAP_SECRET")
            if not api_key:
                return

            lat = device_config.get_config("latitude", default=None)
            lon = device_config.get_config("longitude", default=None)
            if not lat or not lon:
                return

            url = f"https://api.openweathermap.org/data/2.5/alerts?lat={lat}&lon={lon}&appid={api_key}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return

            data = resp.json()
            alerts = data.get("alerts", [])

            if alerts:
                from refresh_task import WeatherAlertInterrupt
                for alert in alerts[:1]:  # Only queue one alert at a time
                    interrupt = WeatherAlertInterrupt(alert)
                    self.queue_interrupt(interrupt)

        except Exception as e:
            logger.warning(f"Failed to check weather alerts: {e}")

    def _fetch_upcoming_events(self, calendar_url, current_dt, tz, threshold_minutes):
        """Fetch events starting within the next threshold_minutes."""
        try:
            import icalendar
            import recurring_ical_events

            if calendar_url.startswith("webcal://"):
                calendar_url = calendar_url.replace("webcal://", "https://")

            resp = requests.get(calendar_url, timeout=15)
            resp.raise_for_status()
            cal = icalendar.Calendar.from_ical(resp.text)

            # Look for events in the next threshold_minutes
            start = current_dt
            end = current_dt + timedelta(minutes=threshold_minutes)
            events = recurring_ical_events.of(cal).between(start, end)

            upcoming = []
            for event in events:
                dtstart = event.decoded("dtstart")
                if isinstance(dtstart, datetime):
                    dtstart = dtstart.astimezone(tz)

                upcoming.append({
                    "title": str(event.get("summary", "")),
                    "start": dtstart,
                    "minutes_until": int((dtstart - current_dt).total_seconds() / 60),
                })

            return upcoming

        except Exception as e:
            logger.warning(f"Failed to fetch calendar for interrupts: {e}")
            return []

    def _get_next_plugin(self, mode_playlists, playlist_manager, mode):
        """Get the next plugin from the mode's playlist list."""
        rotate = mode.get("rotate", False)

        # Find the first playlist that has plugins
        for pl_name in mode_playlists:
            playlist = playlist_manager.get_playlist(pl_name)
            if not playlist or not playlist.plugins:
                continue

            if rotate:
                # Round-robin through plugins
                plugin = playlist.get_next_plugin()
                return plugin, pl_name
            else:
                # For photo frame, just get the current/first plugin
                if playlist.current_plugin_index is not None:
                    idx = playlist.current_plugin_index % len(playlist.plugins)
                else:
                    idx = 0
                    playlist.current_plugin_index = 0
                return playlist.plugins[idx], pl_name

        return None, None

    def _is_in_window(self, current_time, start, end):
        """Check if current_time falls within the start-end window."""
        if start <= end:
            return start <= current_time < end
        else:
            # Wraps past midnight
            return current_time >= start or current_time < end

    def _window_minutes(self, mode):
        """Calculate window duration in minutes for priority sorting."""
        start = mode.get("start_time", "00:00")
        end = mode.get("end_time", "24:00")
        try:
            s_h, s_m = map(int, start.split(":"))
            e_h, e_m = map(int, end.split(":"))
            s_total = s_h * 60 + s_m
            e_total = e_h * 60 + e_m
            if e_total <= s_total:
                e_total += 24 * 60
            return e_total - s_total
        except (ValueError, AttributeError):
            return 1440

    def _fallback_sleep(self, current_dt):
        """When no mode is active, use default cycle interval."""
        default_sleep = self.config.get_config("plugin_cycle_interval_seconds", default=3600)
        return None, default_sleep

    def _get_default_sleep(self):
        return self.config.get_config("plugin_cycle_interval_seconds", default=3600)

    def get_status(self):
        """Return current scheduler status for the web UI."""
        return {
            "enabled": self.is_enabled(),
            "current_mode": self._current_mode,
            "modes_count": len(self.modes),
            "interrupts_queued": len(self._interrupt_queue)
        }
