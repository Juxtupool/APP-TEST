import json
import logging
import os
import webview
from pathlib import Path
from typing import Dict

from app.core import BaseService, safe_api, ApiResponse

from .services.profile_service import ProfileService
from .services.macro_execution_service import MacroExecutionService
from .services.macro_recording_service import MacroRecordingService
from .services.window_control_service import WindowControlService
from .services.serial_service import SerialService
from .services.knob_controller import KnobController
from .services.profile_switcher_service import ProfileSwitcherService
from .services.firmware_update_service import FirmwareUpdateService
from .services.community_library_service import CommunityLibraryService
from .services.update_manager import UpdateManager
from .services.app_icon_service import AppIconService
from .utils.thread_safe_ui import get_ui_bridge

# Import Handlers (Mixins)
from .handlers.profile_handler import ProfileMixin
from .handlers.serial_handler import SerialMixin
from .handlers.system_handler import SystemMixin
from .handlers.community_handler import CommunityMixin
from .handlers.icon_handler import IconMixin
from .handlers.update_handler import UpdateMixin
from .handlers.macro_handler import MacroMixin

# Configure logging path (kept here for app initialization)
log_dir = Path(os.getenv('APPDATA')) / "Overcontrol"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "overcontrol.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler()
    ]
)

APP_ROOT = Path(__file__).parent.parent
PROFILE_PATH = APP_ROOT / "profiles.json"
CONFIG_PATH = APP_ROOT / "config.json"

class Api(
    BaseService,
    ProfileMixin, 
    SerialMixin, 
    SystemMixin, 
    CommunityMixin, 
    IconMixin, 
    UpdateMixin, 
    MacroMixin
):
    def __init__(self):
        super().__init__() # Initialize BaseService (logger)
        
        # Expose important properties to mixins
        self._app_root = APP_ROOT
        self._webview = webview
        
        # Load configuration
        self._config = self._load_config()
        
        # Initialize services
        self._profile_service = ProfileService(PROFILE_PATH)
        self._macro_execution_service = MacroExecutionService()
        self._macro_recording_service = MacroRecordingService()
        self._window_control_service = WindowControlService()
        self._serial_service = SerialService()
        self._knob_controller = KnobController(self._execute_knob_callback)
        self._ui_bridge = get_ui_bridge()
        
        # Initialize additional services
        self._firmware_update_service = FirmwareUpdateService(self._config)
        self._community_library_service = CommunityLibraryService(self._config)
        self._update_manager = UpdateManager(self._config)
        self._app_icon_service = AppIconService()
        
        # Profile switcher with callback
        self._profile_switcher = ProfileSwitcherService(
            self._config, 
            on_profile_switch=self._auto_switch_profile
        )
        
        # State
        self._profiles = self._profile_service.load_profiles()
        self._current_profile_name = self._profiles.get("active_profile", "Default Profile")
        
        # Notify initial state for revert logic
        if self._current_profile_name:
            self._profile_switcher.notify_manual_switch(self._current_profile_name)
            
        self.tray_enabled = self._profiles.get("minimize_to_tray", False)
        self.current_theme = "dark" # Enforce dark theme
        self.current_accent_color = self._profiles.get("accent_color", "#2563eb")
        # Load firmware version from config, default to Unknown if missing
        self.firmware_version = self._config.get('firmware', {}).get('current_version', 'Unknown')
        self.tray_icon = None
        self._tray_update_callback = None
        
        # Callbacks
        self._serial_service.on_message_callback = self.on_serial_message
        self._serial_service.on_connection_lost_callback = self.on_serial_connection_lost
        
        self._window = None
        self._icon_cache = None
        
        # Start profile switcher
        self._profile_switcher.start()
        
        self.logger.info("API initialized successfully")

    def set_window(self, window):
        self._window = window
        self._community_library_service.set_window(window)
        self._ui_bridge.set_window(window)
        
        # Pass bridge to recording service
        self._macro_recording_service.set_ui_bridge(self._ui_bridge)
        
        self.logger.info("Window reference set")

    def set_tray_update_callback(self, callback):
        """Register a callback to refresh the system tray."""
        self._tray_update_callback = callback

    def update_tray(self):
        """Trigger a tray refresh if a callback is registered."""
        if self._tray_update_callback:
            # Run on a separate thread if needed, but pystray items can be updated from any thread
            # however, refreshing the whole menu/icon might be safer in main or via a flag
            self._tray_update_callback()

    def _load_config(self) -> Dict:
        """Load configuration from config.json."""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, 'r') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"Config file not found at {CONFIG_PATH}")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
    
    def _save_config(self):
        """Save configuration to config.json."""
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self._config, f, indent=4)
            self.logger.info("Configuration saved")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

    def _send_toast_notification(self, title, message):
        """Send a Windows Toast Notification using PowerShell."""
        import subprocess
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Overcontrol")
        $notifier.Show($notification)
        """
        try:
            subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.logger.error(f"Failed to send toast: {e}")

    def _auto_switch_profile(self, profile_name: str):
        """Callback for automatic profile switching."""
        try:
            if profile_name in self._profiles.get("profiles", {}):
                result = self.set_active_profile(profile_name, is_auto=True)
                # Check for success using new ApiResponse format (status) OR allow safe_api to wrap set_active_profile
                # set_active_profile now returns ApiResponse dict
                if result.get('status') == 'success':
                    if self._window:
                        safe_name = json.dumps(profile_name)
                        self._ui_bridge.evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")
                    self._send_toast_notification(f"Profile Switched to {profile_name}", "")
                    self.logger.info(f"Auto-switched to profile: {profile_name}")
                else:
                    self.logger.error(f"Failed to auto-switch to profile: {profile_name}")
        except Exception as e:
            self.logger.error(f"Error in auto-switch callback: {e}")

    @safe_api
    def on_serial_message(self, message: str):
        """Handle serial message with thread-safe UI updates."""
        if message.startswith("VERSION_"):
            version = message.replace("VERSION_", "").strip()
            self.firmware_version = version
            
            # Persist the detected version to config
            if 'firmware' not in self._config:
                self._config['firmware'] = {}
            self._config['firmware']['current_version'] = version
            self._save_config()
            
            self.logger.info(f"Firmware version detected and saved: {version}")
            if self._window:
                safe_version = json.dumps(version)
                self._ui_bridge.evaluate_js_safe(f"window.onFirmwareVersion({safe_version})")
            self.update_tray() # Sync tray with connection
            return ApiResponse.success()
        
        self._handle_serial_command(message)
        
        if self._window:
            safe_msg = json.dumps(message)
            self._ui_bridge.evaluate_js_safe(f"window.onSerialMessage({safe_msg})")
        return ApiResponse.success()

    def on_serial_connection_lost(self):
        """Handle connection loss with thread-safe UI update."""
        self.logger.warning("Serial connection lost")
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")
        self.update_tray()

    @safe_api
    def browse_file_or_app(self):
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}
    
    @safe_api
    def get_app_icon(self, app_name: str):
        """Get application icon as base64 data URI."""
        # Check if service returns string or None (as refactored)
        icon_data = self._app_icon_service.get_app_icon(app_name)
        if icon_data:
            return {"status": "success", "icon": icon_data}
        else:
            return ApiResponse.error("Icon not found")
