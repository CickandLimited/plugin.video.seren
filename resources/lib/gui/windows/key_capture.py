from resources.lib.database.skinManager import SkinManager
from resources.lib.gui.windows.base_window import BaseWindow
from resources.lib.modules.globals import g


class KeyCaptureWindow(BaseWindow):
    def __init__(self, xml_file, xml_location, on_capture=None, title="", description=""):
        super().__init__(xml_file, xml_location)
        self._on_capture = on_capture
        self.closed = False
        self.setProperty("key_capture.title", title)
        self.setProperty("key_capture.description", description)

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


def capture_key(setting_id, title_id, description_id, notification_id):
    def _store_key(action_id, button_code):
        codes = []
        if button_code and button_code > 0:
            codes.append(button_code)
        if action_id and action_id > 0 and action_id not in codes:
            codes.append(action_id)
        if not codes:
            return
        value = ":".join(str(code) for code in codes)
        g.set_setting(setting_id, value)
        g.notification(g.ADDON_NAME, g.get_language_string(notification_id).format(value))

    window = KeyCaptureWindow(
        *SkinManager().confirm_skin_path("key_capture.xml"),
        on_capture=_store_key,
        title=g.get_language_string(title_id),
        description=g.get_language_string(description_id),
    )
    window.doModal()
    del window


def capture_snooze_key():
    capture_key("smart_sleep.snooze_key_code", 30670, 30669, 30671)


def capture_manual_key():
    capture_key("smart_sleep.manual_key_code", 30674, 30673, 30675)
