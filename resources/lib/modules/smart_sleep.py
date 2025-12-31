from datetime import datetime, time, timedelta

import xbmc

from resources.lib.database.skinManager import SkinManager
from resources.lib.gui.windows.smart_sleep import SmartSleepWindow
from resources.lib.gui.windows.smart_sleep_debug import SmartSleepDebugWindow
from resources.lib.modules.globals import g


class SmartSleepManager:
    def __init__(self):
        self._dialog = None
        self._debug_dialog = None
        self._countdown_deadline = None
        self._countdown_total_seconds = None
        self._countdown_armed_at = None
        self._next_trigger = None

    def tick(self, monitor=None):
        if monitor and monitor.abortRequested():
            self.close()
            return

        debug_mode = g.get_bool_setting("smart_sleep.debug_mode")
        enabled = g.get_bool_setting("smart_sleep.enabled")
        if not enabled and not debug_mode:
            self._reset_state(clear_snooze=True, close_dialog=True, close_debug=True, clear_arming=True)
            return

        start_time = self._parse_start_time(g.get_setting("smart_sleep.start_time"))
        end_time = self._parse_end_time(g.get_setting("smart_sleep.end_time"))
        now = datetime.now(g.LOCAL_TIMEZONE)
        if not start_time or not end_time:
            self._reset_state(
                clear_snooze=True,
                close_dialog=not debug_mode,
                close_debug=not debug_mode,
                clear_arming=True,
            )
            if debug_mode:
                self._ensure_main_dialog()
                self._update_dialog(now)
                self._ensure_debug_dialog()
                self._update_debug_dialog(
                    now,
                    start_time,
                    end_time,
                    None,
                    None,
                    "invalid schedule",
                    enabled,
                )
            return

        window_state = self._get_window_state(now, start_time, end_time)
        self._next_trigger = window_state["next_trigger"]

        snooze_until = self._get_snooze_until()
        if snooze_until:
            if snooze_until >= window_state["end"]:
                self._clear_snooze_until()
                snooze_until = None

        in_window = window_state["active"] and enabled
        reason = "waiting for window"

        if in_window:
            if snooze_until and now < snooze_until:
                reason = "snoozed"
                if not debug_mode:
                    self._reset_state(close_dialog=True, clear_arming=True)
                    return
                self._clear_countdown_arming()
                self._clear_countdown()
            else:
                if snooze_until and now >= snooze_until:
                    self._clear_snooze_until()
                    snooze_until = None
                if self._countdown_armed_at is None:
                    self._countdown_armed_at = now
                    g.log("Smart sleep countdown delay armed", "debug")
                delay_deadline = self._countdown_armed_at + timedelta(seconds=10)
                if now < delay_deadline:
                    reason = "arming delay"
                    self._clear_countdown()
                    self._close_main_dialog()
                    if not debug_mode:
                        return
                else:
                    if self._countdown_deadline is None:
                        g.log("Smart sleep countdown delay elapsed", "debug")
                        self._start_countdown(now)
                    self._ensure_main_dialog()
                    self._update_dialog(now)
                    if self._countdown_deadline and now >= self._countdown_deadline:
                        self._complete_shutdown()
                        return
                    reason = "counting down"
        else:
            reason = "disabled" if not enabled else "waiting for window"
            if not debug_mode:
                self._reset_state(clear_snooze=True, close_dialog=True, clear_arming=True)
                return
            self._clear_snooze_until()
            self._clear_countdown_arming()
            self._clear_countdown()
            self._ensure_main_dialog()
            self._update_dialog(now)

        if debug_mode:
            self._ensure_debug_dialog()
            self._update_debug_dialog(
                now,
                start_time,
                end_time,
                window_state,
                snooze_until,
                reason,
                enabled,
            )
        else:
            self._close_debug_dialog()

    def close(self):
        self._reset_state(close_dialog=True, close_debug=True)

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

    def _clear_countdown(self):
        self._countdown_deadline = None
        self._countdown_total_seconds = None

    def _update_dialog(self, now):
        if not self._countdown_deadline:
            countdown_text = "--:--"
        else:
            remaining = max(0, int((self._countdown_deadline - now).total_seconds()))
            countdown_text = self._format_duration(remaining)
        self._dialog.set_countdown_text(countdown_text)

    def _handle_cancel(self):
        now = datetime.now(g.LOCAL_TIMEZONE)
        self._snooze(now)

    def _snooze(self, now):
        snooze_minutes = max(1, g.get_int_setting("smart_sleep.snooze_minutes", 15))
        snooze_until = now + timedelta(minutes=snooze_minutes)
        self._set_snooze_until(snooze_until)
        g.log(f"Smart sleep snoozed until {snooze_until.isoformat()}", "info")
        self._reset_state(close_dialog=True, clear_arming=True)

    def _complete_shutdown(self):
        self._reset_state(clear_snooze=True, close_dialog=True, close_debug=True, clear_arming=True)
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

    def _ensure_main_dialog(self):
        if self._dialog and self._dialog.closed:
            self._dialog = None
        if not self._dialog:
            self._dialog = SmartSleepWindow(
                *SkinManager().confirm_skin_path("smart_sleep.xml"), on_cancel=self._handle_cancel
            )
            self._dialog.show()

    def _ensure_debug_dialog(self):
        if self._debug_dialog and self._debug_dialog.closed:
            self._debug_dialog = None
        if not self._debug_dialog:
            self._debug_dialog = SmartSleepDebugWindow(*SkinManager().confirm_skin_path("smart_sleep_debug.xml"))
            self._debug_dialog.show()

    def _close_debug_dialog(self):
        if self._debug_dialog:
            try:
                self._debug_dialog.close()
            finally:
                self._debug_dialog = None

    def _close_main_dialog(self):
        if self._dialog:
            try:
                self._dialog.close()
            finally:
                self._dialog = None

    def _format_duration(self, total_seconds):
        total_seconds = max(0, int(total_seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _format_time(self, value, with_seconds=False):
        if not value:
            return "--"
        if isinstance(value, datetime):
            fmt = "%H:%M:%S" if with_seconds else "%H:%M"
            return value.strftime(fmt)
        return f"{value.hour:02d}:{value.minute:02d}"

    def _update_debug_dialog(self, now, start_time, end_time, window_state, snooze_until, reason, enabled):
        if not self._debug_dialog:
            return
        active = enabled and window_state and window_state.get("active")
        countdown_remaining = "--:--"
        if self._countdown_deadline:
            countdown_remaining = self._format_duration((self._countdown_deadline - now).total_seconds())
        snooze_remaining = "--"
        if snooze_until and now < snooze_until:
            snooze_remaining = self._format_duration((snooze_until - now).total_seconds())
        next_trigger = "--"
        if window_state and window_state.get("next_trigger"):
            next_trigger = window_state["next_trigger"].strftime("%Y-%m-%d %H:%M")
        info = {
            "active": "Yes" if active else "No",
            "current_time": self._format_time(now, with_seconds=True),
            "start_time": self._format_time(start_time),
            "end_time": self._format_time(end_time),
            "countdown_remaining": countdown_remaining,
            "snooze_remaining": snooze_remaining,
            "next_trigger": next_trigger,
            "state_reason": reason,
        }
        self._debug_dialog.update_info(info)

    def _reset_state(self, clear_snooze=False, close_dialog=False, close_debug=False, clear_arming=False):
        if clear_snooze:
            self._clear_snooze_until()
        if close_dialog:
            self._close_main_dialog()
        if close_debug:
            self._close_debug_dialog()
        if clear_arming:
            self._clear_countdown_arming()
        self._clear_countdown()

    def _clear_countdown_arming(self):
        self._countdown_armed_at = None
