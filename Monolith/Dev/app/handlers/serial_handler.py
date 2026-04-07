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

