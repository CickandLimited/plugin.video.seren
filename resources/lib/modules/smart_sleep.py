from datetime import datetime, time, timedelta

import xbmc
import xbmcgui

from resources.lib.modules.globals import g


class SmartSleepManager:
    def __init__(self):
        self._dialog = None
        self._countdown_deadline = None
        self._countdown_total_seconds = None
        self._next_trigger = None

    def tick(self, monitor=None):
        if monitor and monitor.abortRequested():
            self.close()
            return

        if not g.get_bool_setting("smart_sleep.enabled"):
            self._reset_state(clear_snooze=True)
            return

        start_time = self._parse_start_time(g.get_setting("smart_sleep.start_time"))
        if not start_time:
            return

        now = datetime.now(g.LOCAL_TIMEZONE)
        start_dt = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)

        if now < start_dt:
            self._next_trigger = start_dt
            self._reset_state(clear_snooze=True, close_dialog=True)
            return

        self._next_trigger = start_dt + timedelta(days=1)
        snooze_until = self._get_snooze_until()
        if snooze_until:
            if snooze_until <= start_dt:
                self._clear_snooze_until()
                snooze_until = None
            elif now < snooze_until:
                self._reset_state(close_dialog=True)
                return
            else:
                self._clear_snooze_until()

        if self._countdown_deadline is None:
            self._start_countdown(now)

        if not self._dialog:
            self._dialog = xbmcgui.DialogProgress()
            self._dialog.create(g.get_language_string(30645), "")

        if self._dialog.iscanceled():
            self._snooze(now)
            return

        self._update_dialog(now)

        if now >= self._countdown_deadline:
            self._complete_shutdown()

    def close(self):
        self._reset_state(close_dialog=True)

    def _parse_start_time(self, value):
        if not value:
            return None
        try:
            parts = value.strip().split(":")
            if len(parts) < 2:
                return None
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (TypeError, ValueError):
            g.log(f"Invalid smart sleep start time '{value}'", "warning")
            return None

    def _get_snooze_until(self):
        value = g.get_setting("smart_sleep.snooze_until")
        if not value:
            return None
        try:
            snooze_dt = datetime.fromisoformat(value)
            if snooze_dt.tzinfo is None:
                snooze_dt = snooze_dt.replace(tzinfo=g.LOCAL_TIMEZONE)
            return snooze_dt.astimezone(g.LOCAL_TIMEZONE)
        except ValueError:
            g.log(f"Invalid smart sleep snooze timestamp '{value}'", "warning")
            self._clear_snooze_until()
            return None

    def _clear_snooze_until(self):
        g.set_setting("smart_sleep.snooze_until", "")

    def _set_snooze_until(self, timestamp):
        g.set_setting("smart_sleep.snooze_until", timestamp.isoformat())

    def _start_countdown(self, now):
        minutes = max(1, g.get_int_setting("smart_sleep.countdown_minutes", 10))
        self._countdown_total_seconds = minutes * 60
        self._countdown_deadline = now + timedelta(seconds=self._countdown_total_seconds)
        g.log(f"Smart sleep countdown started for {minutes} minutes", "info")

    def _update_dialog(self, now):
        remaining = max(0, int((self._countdown_deadline - now).total_seconds()))
        percent = 0
        if self._countdown_total_seconds:
            percent = int((self._countdown_total_seconds - remaining) / self._countdown_total_seconds * 100)
        minutes_left = max(1, int((remaining + 59) / 60))
        message = g.get_language_string(30650).format(minutes=minutes_left)
        self._dialog.update(percent, message)

    def _snooze(self, now):
        snooze_minutes = max(1, g.get_int_setting("smart_sleep.snooze_minutes", 15))
        snooze_until = now + timedelta(minutes=snooze_minutes)
        self._set_snooze_until(snooze_until)
        g.log(f"Smart sleep snoozed until {snooze_until.isoformat()}", "info")
        self._reset_state(close_dialog=True)

    def _complete_shutdown(self):
        self._reset_state(clear_snooze=True, close_dialog=True)
        g.log("Smart sleep countdown completed, powering down", "info")
        try:
            xbmc.executebuiltin("CECStandby")
        except Exception as exc:  # pylint: disable=broad-except
            g.log(f"CECStandby failed: {exc}", "warning")
        try:
            xbmc.executebuiltin("Powerdown")
        except Exception as exc:  # pylint: disable=broad-except
            g.log(f"Powerdown failed, trying Shutdown: {exc}", "warning")
            try:
                xbmc.executebuiltin("Shutdown")
            except Exception as shutdown_exc:  # pylint: disable=broad-except
                g.log(f"Shutdown failed: {shutdown_exc}", "warning")

    def _reset_state(self, clear_snooze=False, close_dialog=False):
        if clear_snooze:
            self._clear_snooze_until()
        if close_dialog and self._dialog:
            try:
                self._dialog.close()
            finally:
                self._dialog = None
        self._countdown_deadline = None
        self._countdown_total_seconds = None
