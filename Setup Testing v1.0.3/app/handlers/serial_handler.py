import logging

logger = logging.getLogger(__name__)

class SerialMixin:
    def get_serial_ports(self):
        return self._serial_service.get_available_ports()

    def connect_serial(self, port):
        import json
        success = self._serial_service.connect(port)
        if success:
            if hasattr(self, '_window') and self._window:
                safe_port = json.dumps(port)
                self._ui_bridge.evaluate_js_safe(f"window.onSerialConnected({safe_port})")
            self.update_tray()
        return {"status": "success" if success else "error", "connected": success}

    def disconnect_serial(self):
        self._serial_service.disconnect()
        if hasattr(self, '_window') and self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")
        self.update_tray()
        return {"status": "success"}
    
    def is_connected(self):
        return self._serial_service.is_connected
