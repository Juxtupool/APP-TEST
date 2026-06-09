import logging
import json
from app.core import safe_api, ApiResponse

logger = logging.getLogger(__name__)

class UpdateMixin:
    @safe_api
    def check_for_updates(self):
        """Check GitHub for both Firmware and App updates."""
        try:
            firmware_result = self._firmware_update_service.check_firmware_updates(self.firmware_version)
            app_result = self._update_manager.check_app_update()
            
            return {
                "status": "success", 
                "firmware": firmware_result,
                "app": app_result
            }
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            return {"status": "error", "message": str(e)}

    @safe_api
    def check_firmware_updates(self):
        """Check specifically for firmware updates."""
        try:
             return self._firmware_update_service.check_firmware_updates(self.firmware_version)

        except Exception as e:
            logger.error(f"Error checking firmware updates: {e}")
            return {"status": "error", "message": str(e)}

    @safe_api
    def check_app_updates(self):
        """Check specifically for app updates."""
        try:
            return self._update_manager.check_app_update()
        except Exception as e:
            logger.error(f"Error checking app updates: {e}")
            return {"status": "error", "message": str(e)}

    @safe_api
    def download_app_update(self, download_url):
        """Download app update using UpdateManager."""
        return self._update_manager.download_update(download_url)

    @safe_api
    def trigger_app_restart(self):
        """Trigger non-blocking restart sequence."""
        return self._update_manager.trigger_restart()
    
    @safe_api
    def download_firmware_update(self, download_url: str):
        """Download firmware update from GitHub."""
        try:
            save_path = self._app_root / "firmware" / "update.uf2"
            success = self._firmware_update_service.download_firmware(download_url, save_path)
            
            if success:
                return {"status": "success", "path": str(save_path)}
            else:
                return {"status": "error", "message": "Download failed"}
        except Exception as e:
            logger.error(f"Error downloading firmware: {e}")
            return {"status": "error", "message": str(e)}
            
    @safe_api
    def get_firmware_version(self):
        return {"status": "success", "version": self.firmware_version}

    @safe_api
    def get_app_version(self):
        from ..version import APP_VERSION
        return {"status": "success", "version": APP_VERSION}

    @safe_api
    def select_firmware_file(self):
        result = self._window.create_file_dialog(self._webview.OPEN_DIALOG, file_types=("UF2 Files (*.uf2)", "Bin Files (*.bin)", "All Files (*.*)"))
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}

    @safe_api
    def flash_firmware(self, port, file_path):
        from ..services.flasher_service import FlasherService
        import serial.tools.list_ports
        
        # 1. Try to get port from active connection
        if not port and self._serial_service.is_connected:
            port = self._serial_service.port
            logger.info(f"Using currently connected port: {port}")

        # 2. If still no port, scan for available ports
        if not port:
            ports = list(serial.tools.list_ports.comports())
            if ports:
                # Heuristic: Pick the first USB-to-UART bridge or CP210x
                # For now, just pick the first available port
                port = ports[0].device
                logger.info(f"Auto-detected port: {port} from {len(ports)} candidates")
            else:
                 return {"status": "error", "message": "No device found. Please connect via USB."}

        # Ensure we are disconnected before flashing
        if self._serial_service.is_connected:
            logger.info("Disconnecting serial for flashing...")
            self._serial_service.disconnect()
            import time
            time.sleep(0.5)

        def on_progress(msg, pct):
            if self._window:
                try:
                    # Escape quotes for JS
                    safe_msg = json.dumps(msg)
                    # We send pct as second arg now
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashProgress({safe_msg}, {pct})")
                except Exception as e:
                    logger.error(f"Error sending flash progress: {e}")

        def on_finished(success, msg):
            if self._window:
                try:
                    safe_msg = json.dumps(msg)
                    js_bool = "true" if success else "false"
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashFinished({js_bool}, {safe_msg})")
                    logger.info(f"Flash finished: success={success}")
                except Exception as e:
                    logger.error(f"Error sending flash completion: {e}")
            
        self._flasher = FlasherService(on_progress, on_finished)
        
        success, info = self._flasher.flash(port, file_path)
        
        return {"status": "success" if success else "error", "message": info}
