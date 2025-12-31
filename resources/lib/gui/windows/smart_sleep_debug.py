from resources.lib.gui.windows.base_window import BaseWindow
from resources.lib.modules.globals import g


class SmartSleepDebugWindow(BaseWindow):
    def __init__(self, xml_file, xml_location):
        super().__init__(xml_file, xml_location)
        self.closed = False
        self._apply_style_properties()

    def _apply_style_properties(self):
        font_size = g.get_int_setting("smart_sleep.font_size", 28)
        opacity = g.get_int_setting("smart_sleep.panel_opacity", 200)
        opacity = max(0, min(255, opacity))

        self.setProperty("smart_sleep.debug.font", f"font{font_size}")
        self.setProperty("smart_sleep.debug.panel.color", f"{opacity:02X}000000")

    def update_info(self, info):
        for key, value in info.items():
            self.setProperty(f"smart_sleep.debug.{key}", str(value))

    def close(self):
        self.closed = True
        super().close()

    def handle_action(self, action_id, control_id=None):
        return
