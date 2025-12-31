from resources.lib.database.skinManager import SkinManager
from resources.lib.gui.windows.base_window import BaseWindow
from resources.lib.modules.globals import g


class KeyCaptureWindow(BaseWindow):
    def __init__(self, xml_file, xml_location, on_capture=None):
        super().__init__(xml_file, xml_location)
        self._on_capture = on_capture
        self.closed = False

    def onAction(self, action):
        if self.closed:
            return
        action_id = action.getId()
        button_code = action.getButtonCode()
        if action_id == 0 and not button_code:
            return
        if self._on_capture:
            self._on_capture(action_id, button_code)
        self.close()

    def handle_action(self, action_id, control_id=None):
        return

    def close(self):
        self.closed = True
        super().close()


def capture_snooze_key():
    def _store_key(action_id, button_code):
        codes = []
        if button_code and button_code > 0:
            codes.append(button_code)
        if action_id and action_id > 0 and action_id not in codes:
            codes.append(action_id)
        if not codes:
            return
        value = ":".join(str(code) for code in codes)
        g.set_setting("smart_sleep.snooze_key_code", value)
        g.notification(g.ADDON_NAME, g.get_language_string(30671).format(value))

    window = KeyCaptureWindow(*SkinManager().confirm_skin_path("key_capture.xml"), on_capture=_store_key)
    window.doModal()
    del window
