from resources.lib.gui.windows.base_window import BaseWindow
from resources.lib.modules.globals import g


class SmartSleepWindow(BaseWindow):
    CANCEL_BUTTON_ID = 3001

    def __init__(self, xml_file, xml_location, on_cancel=None):
        super().__init__(xml_file, xml_location)
        self._on_cancel = on_cancel
        self.closed = False
        self._apply_style_properties()

    def _apply_style_properties(self):
        panel_x = g.get_int_setting("smart_sleep.widget_x", 20)
        panel_y = g.get_int_setting("smart_sleep.widget_y", 20)
        font_size = g.get_int_setting("smart_sleep.font_size", 28)
        opacity = g.get_int_setting("smart_sleep.panel_opacity", 200)
        opacity = max(0, min(255, opacity))

        self.setProperty("smart_sleep.panel.x", str(panel_x))
        self.setProperty("smart_sleep.panel.y", str(panel_y))
        self.setProperty("smart_sleep.font", f"font{font_size}")
        self.setProperty("smart_sleep.panel.color", f"{opacity:02X}000000")

    def set_countdown_text(self, text):
        self.setProperty("smart_sleep.countdown.text", text)

    def handle_action(self, action_id, control_id=None):
        if action_id == 7 and control_id == self.CANCEL_BUTTON_ID:
            self._cancel()

    def _cancel(self):
        if self.closed:
            return
        self.close()
        if self._on_cancel:
            self._on_cancel()

    def close(self):
        self.closed = True
        super().close()
