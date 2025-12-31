from datetime import datetime, time, timedelta

import xbmc

from resources.lib.database.skinManager import SkinManager
from resources.lib.gui.windows.smart_sleep import SmartSleepWindow
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
        end_time = self._parse_end_time(g.get_setting("smart_sleep.end_time"))
        if not start_time or not end_time:
            return

        now = datetime.now(g.LOCAL_TIMEZONE)
        window_state = self._get_window_state(now, start_time, end_time)
        if not window_state["active"]:
            self._next_trigger = window_state["next_trigger"]
            self._reset_state(clear_snooze=True, close_dialog=True)
            return

        self._next_trigger = window_state["next_trigger"]
        snooze_until = self._get_snooze_until()
        if snooze_until:
            if snooze_until >= window_state["end"]:
                self._clear_snooze_until()
                snooze_until = None
            elif now < snooze_until:
                self._reset_state(close_dialog=True)
                return
            else:
                self._clear_snooze_until()

        if self._countdown_deadline is None:
            self._start_countdown(now)

        if self._dialog and self._dialog.closed:
            self._dialog = None

        if not self._dialog:
            self._dialog = SmartSleepWindow(
                *SkinManager().confirm_skin_path("smart_sleep.xml"), on_cancel=self._handle_cancel
            )
            self._dialog.show()

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

    def _parse_end_time(self, value):
        if not value:
            return None
        try:
            parts = value.strip().split(":")
            if len(parts) < 2:
                return None
            return time(hour=int(parts[0]), minute=int(parts[1]))
        except (TypeError, ValueError):
            g.log(f"Invalid smart sleep end time '{value}'", "warning")
            return None

    def _get_window_state(self, now, start_time, end_time):
        start_today = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
        end_today = now.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)

        if start_time <= end_time:
            if now < start_today:
                return {"active": False, "end": end_today, "next_trigger": start_today}
            if now >= end_today:
                return {
                    "active": False,
                    "end": end_today,
                    "next_trigger": start_today + timedelta(days=1),
                }
            return {"active": True, "end": end_today, "next_trigger": start_today + timedelta(days=1)}

        if now >= start_today:
            window_end = end_today + timedelta(days=1)
            return {
                "active": now < window_end,
                "end": window_end,
                "next_trigger": start_today + timedelta(days=1),
            }

        window_start = start_today - timedelta(days=1)
        if now < end_today:
            return {"active": True, "end": end_today, "next_trigger": start_today}
        return {"active": False, "end": end_today, "next_trigger": start_today}

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
        minutes_left, seconds_left = divmod(remaining, 60)
        countdown_text = f"{minutes_left:02d}:{seconds_left:02d}"
        self._dialog.set_countdown_text(countdown_text)

    def _handle_cancel(self):
        now = datetime.now(g.LOCAL_TIMEZONE)
        self._snooze(now)

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
