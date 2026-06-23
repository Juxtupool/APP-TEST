from app.core import safe_api, ApiResponse
import logging
import time
import json

logger = logging.getLogger(__name__)

class SerialMixin:
    @safe_api
    def get_serial_ports(self):
        return self._serial_service.get_available_ports()

    @safe_api
    def connect_serial(self, port):
        success = self._serial_service.connect(port)
        if success:
            if hasattr(self, '_window') and self._window:
                safe_port = json.dumps(port)
                self._ui_bridge.evaluate_js_safe(f"window.onSerialConnected({safe_port})")
            self.update_tray()
            
            # Send current active profile's knob mode to hardware
            if hasattr(self, '_profiles') and hasattr(self, '_current_profile_name'):
                profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
                knob_mode = profile_data.get("knob_mode", "Standard")
                def sync_knob_mode():
                    time.sleep(1.5)
                    if self._serial_service.is_connected:
                        self._serial_service.send_raw_command(f"SET_KNOB_MODE {knob_mode}")
                import threading
                threading.Thread(target=sync_knob_mode, daemon=True).start()

        return ApiResponse.success({"connected": success}) if success else ApiResponse.error("Connection failed")

    @safe_api
    def disconnect_serial(self):
        self._serial_service.disconnect()
        if hasattr(self, '_window') and self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")
        self.update_tray()
        return ApiResponse.success()
    
    @safe_api
    def is_connected(self):
        return self._serial_service.is_connected

