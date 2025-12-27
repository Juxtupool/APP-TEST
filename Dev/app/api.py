import json
import os
import sys
import time
import winreg
import subprocess
import threading
import logging
from pathlib import Path
from typing import Dict, List, Optional
import webview

from .services.profile_service import ProfileService
from .services.macro_execution_service import MacroExecutionService
from .services.serial_service import SerialService
from .services.knob_controller import KnobController
from .services.profile_switcher_service import ProfileSwitcherService
from .services.firmware_update_service import FirmwareUpdateService
from .services.community_library_service import CommunityLibraryService
from .services.update_manager import UpdateManager
from .utils.thread_safe_ui import get_ui_bridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('macropad.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

APP_ROOT = Path(__file__).parent.parent
PROFILE_PATH = APP_ROOT / "profiles.json"
CONFIG_PATH = APP_ROOT / "config.json"

class Api:
    def __init__(self):
        # Load configuration
        self._config = self._load_config()
        
        # Initialize services
        self._profile_service = ProfileService(PROFILE_PATH)
        self._macro_execution_service = MacroExecutionService()
        self._serial_service = SerialService()
        self._knob_controller = KnobController(self._execute_knob_callback)
        self._ui_bridge = get_ui_bridge()
        
        # Initialize new services
        self._firmware_update_service = FirmwareUpdateService(self._config)
        self._community_library_service = CommunityLibraryService(self._config)
        self._update_manager = UpdateManager(self._config)
        
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
        self.current_theme = self._profiles.get("theme", "dark")
        self.firmware_version = "Unknown"  # Firmware version from device
        self.tray_icon = None  # Initialize tray icon reference
        
        # Callbacks
        self._serial_service.on_message_callback = self.on_serial_message
        self._serial_service.on_connection_lost_callback = self.on_serial_connection_lost
        
        self._window = None # To be set after window creation
        
        # Start profile switcher if enabled
        if self._config.get('auto_switching', {}).get('enabled', False):
            self._profile_switcher.start()
        
        # Cache for icons
        self._icon_cache = None
        
        logger.info("API initialized successfully")

    def set_window(self, window):
        """Set window reference and initialize UI bridge."""
        self._window = window
        self._ui_bridge.set_window(window)
        logger.info("Window reference set")

    def window_minimize(self):
        """Minimize the window."""
        if self._window:
            self._window.minimize()

    def window_close(self):
        """Close the window (or hide to tray if enabled)."""
        if self._window:
            # If resizing/drag issues occur, this is the safe close
            self._window.emit('closing') # Trigger on_closing logic in main.py
            # If on_closing returns False (handled), it won't close.
            # But emit('closing') usually just runs listeners.
            # We should call .destroy() or .hide() based on logic.
            # Actually, main.py handles 'closing' event.
            # Let's just call destroy(), which triggers the event? 
            # Usually .destroy() kills it.
            # Let's rely on standard behavior or just call quit logic.
            # Since we have tray logic in main.py, let's just use destroy() which should fire 'closing' event?
            # webview's destroy() might force close.
            # Let's try to mimic the X button behavior.
            self._window.destroy()

    def window_toggle_maximize(self):
        """Toggle maximize/restore."""
        if self._window:
            # Pywebview Window object doesn't always have is_maximized property exposed portably.
            # We'll use toggle_fullscreen for now as a "Max" equivalent for this context, 
            # OR we can try to implement proper maximize if needed.
            # For a macropad app, fullscreen might be too much (hides taskbar).
            # Let's try to find a way to maximize. 
            pass # Pending implementation if needed, for now user can drag edges.
            # We will start with just Minimize and Close.
    
    def _load_config(self) -> Dict:
        """Load configuration from config.json."""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found at {CONFIG_PATH}")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _save_config(self):
        """Save configuration to config.json."""
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self._config, f, indent=4)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def _send_toast_notification(self, title, message):
        """Send a Windows Toast Notification using PowerShell."""
        import subprocess
        # PowerShell script to show toast (ToastText01 is single bold line, but ToastText02 is Title+Text)
        # To make it look like a single line message, we can put everything in header or just use Title + empty body.
        # User requested: "Profile Switched to DaVinic Resolve" in one line.
        # We will pass that as 'title' and leave second line empty.
        
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Macropad Pro")
        $notifier.Show($notification)
        """
        try:
            subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            logger.error(f"Failed to send toast: {e}")

    def _auto_switch_profile(self, profile_name: str):
        """Callback for automatic profile switching."""
        try:
            # Check if profile exists
            if profile_name in self._profiles.get("profiles", {}):
                result = self.set_active_profile(profile_name, is_auto=True)
                if result.get('status') == 'success':
                    # Notify UI (Update dropdowns/state, but NO IN-APP TOAST)
                    if self._window:
                        safe_name = json.dumps(profile_name)
                        self._ui_bridge.evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")
                    
                    # Send System Notification (Single Line as requested)
                    self._send_toast_notification(f"Profile Switched to {profile_name}", "")
                    
                    logger.info(f"Auto-switched to profile: {profile_name}")
                else:
                    logger.error(f"Failed to auto-switch to profile: {profile_name}")
        except Exception as e:
            logger.error(f"Error in auto-switch callback: {e}")

    # --- Profile Methods ---
    def get_profiles(self):
        self._profiles = self._profile_service.load_profiles()
        return self._profiles

    def save_profiles(self, profiles):
        """Save profiles with validation."""
        if not isinstance(profiles, dict):
            logger.error(f"Invalid profiles type: {type(profiles)}")
            return {"status": "error", "message": "Invalid profiles format"}
        
        self._profiles = profiles
        # Ensure active_profile is preserved or updated
        if "active_profile" not in self._profiles:
             self._profiles["active_profile"] = self._current_profile_name
        
        try:
            self._profile_service.save_profiles(profiles)
            logger.info("Profiles saved successfully")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
            return {"status": "error", "message": str(e)}

    def set_active_profile(self, profile_name: str, is_auto: bool = False):
        """Set active profile with validation."""
        if not isinstance(profile_name, str) or not profile_name:
            logger.error("Invalid profile name")
            return {"status": "error", "message": "Invalid profile name"}
        
        # Validate profile exists
        if profile_name not in self._profiles.get("profiles", {}):
            logger.error(f"Profile not found: {profile_name}")
            return {"status": "error", "message": "Profile not found"}
        
        self._current_profile_name = profile_name
        
        # Notify switcher if manual
        if not is_auto and self._profile_switcher:
             self._profile_switcher.notify_manual_switch(profile_name)
             
        logger.info(f"Active profile set to: {profile_name} (Auto: {is_auto})")
        
        # Save active profile setting
        self._profiles["active_profile"] = profile_name
        self._profile_service.save_profiles(self._profiles)
        
        # Set Knob Mode
        profile_data = self._profiles.get("profiles", {}).get(profile_name, {})
        knob_mode = profile_data.get("knob_mode", "Standard")
        knob_speed = profile_data.get("knob_speed", 1)
        self._knob_controller.set_mode(knob_mode)
        self._knob_controller.set_speed(knob_speed)
        
        return {"status": "success"}

    def set_knob_mode(self, mode):
        # Update current profile
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_mode"] = mode
            self._profile_service.save_profiles(self._profiles)
            
        self._knob_controller.set_mode(mode)
        return {"status": "success"}

    def set_knob_speed(self, speed):
        # Update current profile
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_speed"] = speed
            self._profile_service.save_profiles(self._profiles)
            
        self._knob_controller.set_speed(speed)
        return {"status": "success"}
    


    def browse_file_or_app(self):
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}

    # --- Serial Methods ---
    def get_serial_ports(self):
        return self._serial_service.get_available_ports()

    def connect_serial(self, port):
        success = self._serial_service.connect(port)
        return {"status": "success" if success else "error", "connected": success}

    def disconnect_serial(self):
        self._serial_service.disconnect()
        return {"status": "success"}
    
    def is_connected(self):
        return self._serial_service.is_connected

    # --- Macro Methods ---
    def execute_macro(self, macro_data):
        self._macro_execution_service.execute_macro(macro_data)
        return {"status": "success"}

    # --- Settings Methods ---
    def get_startup_status(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "MacropadPro")
            winreg.CloseKey(key)
            return {"status": "success", "enabled": True}
        except WindowsError:
            return {"status": "success", "enabled": False}

    def set_startup_status(self, enabled):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                # Determine path for startup
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}"'
                else:
                    # Dev mode: assume python executable + app/main.py
                    # APP_ROOT is V4_Webview_NodeMCU
                    current_dir = Path(__file__).parent # app/
                    main_script = current_dir / "main.py"
                    cmd = f'"{sys.executable}" "{main_script}"'
                
                winreg.SetValueEx(key, "MacropadPro", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "MacropadPro")
                except WindowsError:
                    pass
            winreg.CloseKey(key)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_tray_status(self):
        return {"status": "success", "enabled": self.tray_enabled}

    def set_tray_status(self, enabled):
        self.tray_enabled = enabled
        self._profiles["minimize_to_tray"] = enabled
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    def get_theme(self):
        return {"status": "success", "theme": self.current_theme}
    
    def get_firmware_version(self):
        return {"status": "success", "version": self.firmware_version}

    def set_theme(self, theme):
        self.current_theme = theme
        self._profiles["theme"] = theme
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    def select_firmware_file(self):
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=("Bin Files (*.bin)", "All Files (*.*)"))
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}

    def flash_firmware(self, port, file_path):
        from .services.flasher_service import FlasherService
        
        # Callbacks for the service
        def on_progress(msg, pct):
            """Thread-safe progress callback."""
            if self._window:
                try:
                    safe_msg = json.dumps(msg)
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashProgress({safe_msg})")
                except Exception as e:
                    logger.error(f"Error sending flash progress: {e}")

        def on_finished(success, msg):
            """Thread-safe completion callback."""
            if self._window:
                try:
                    safe_msg = json.dumps(msg)
                    js_bool = "true" if success else "false"
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashFinished({js_bool}, {safe_msg})")
                    logger.info(f"Flash finished: success={success}")
                except Exception as e:
                    logger.error(f"Error sending flash completion: {e}")

        # Create/Run Service (fresh instance for simplicity or keep one global?)
        # For now, local instance is fine, but we might want to keep reference to cancel later.
        self._flasher = FlasherService(on_progress, on_finished)
        success, info = self._flasher.flash(port, file_path)
        
        return {"status": "success" if success else "error", "message": info}

    def reset_to_defaults(self):
        # Reset profiles to default
        default = self._profile_service.get_default_profile()
        self._profiles = {
            "profiles": {"Default Profile": default},
            "active_profile": "Default Profile",
            "minimize_to_tray": False 
        }
        self.tray_enabled = False
        self._current_profile_name = "Default Profile"
        self._profile_service.save_profiles(self._profiles)
        
        # Reset knob mode too
        # Reset knob mode too
        self._knob_controller.set_mode("Standard")
        self._knob_controller.set_speed(1)
        
        # Reload UI
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.location.reload()")
        
        logger.info("Reset to defaults completed")
        return {"status": "success"}

    # --- Events (Push to JS) ---
    def on_serial_message(self, message: str):
        """Handle serial message with thread-safe UI updates."""
        try:
            # Check for firmware version message
            if message.startswith("VERSION_"):
                version = message.replace("VERSION_", "").strip()
                self.firmware_version = version
                logger.info(f"Firmware version detected: {version}")
                # Push version to frontend
                if self._window:
                    safe_version = json.dumps(version)
                    self._ui_bridge.evaluate_js_safe(f"window.onFirmwareVersion({safe_version})")
                return
            
            # 1. Execute Macro
            self._handle_serial_command(message)
            
            # 2. Push to JS
            if self._window:
                safe_msg = json.dumps(message)
                self._ui_bridge.evaluate_js_safe(f"window.onSerialMessage({safe_msg})")
        except Exception as e:
            logger.error(f"Error handling serial message '{message}': {e}")

    def on_serial_connection_lost(self):
        """Handle connection loss with thread-safe UI update."""
        logger.warning("Serial connection lost")
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")

    def _handle_serial_command(self, message: str):
        """Handle serial command with proper error handling."""
        try:
            if message in ["KNOB_LEFT", "KNOB_RIGHT", "KNOB_PRESS"]:
                self._knob_controller.handle_input(message)
                return

            profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
            macro_name = None
            
            if message.startswith("KEY_") and message.endswith("_PRESSED"):
                # Extract key index
                # NOTE: Firmware sends 0-indexed (KEY_0, KEY_1, etc)
                # But profile uses 1-indexed keys ("1", "2", etc) to match UI
                # So we add +1 to convert firmware index to profile key
                try:
                    idx = int(message.split("_")[1]) + 1
                    logger.debug(f"Key {idx} pressed")
                except (ValueError, IndexError) as e:
                    logger.error(f"Invalid key message format: {message}")
                    return
                
                # Get assigned macro
                macro_name = profile_data.get("keys", {}).get(str(idx))
            
            if macro_name:
                self._execute_macro_by_name(macro_name, profile_data)
                        
        except Exception as e:
            logger.error(f"Error handling serial command '{message}': {e}", exc_info=True)

    def _execute_knob_callback(self, command: str):
        """Execute knob callback with proper logging."""
        profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
        current_mode = self._knob_controller.mode
        logger.debug(f"Knob Callback - Command: {command}, Mode: {current_mode}")
        macro_name = None
        
        if current_mode == "Standard":
            # Preset: Volume Control
            if command == "KNOB_LEFT":
                logger.debug("Executing Volume Down")
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["voldown"]})
            elif command == "KNOB_RIGHT":
                logger.debug("Executing Volume Up")
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["volup"]})
            elif command == "KNOB_PRESS":
                logger.debug("Executing Mute")
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["volumemute"]})
        

                
        elif current_mode == "Custom" or current_mode == "Timeline Scrubber":
            if command == "KNOB_LEFT":
                macro_name = profile_data.get("knobs", {}).get("knob_rotate_left")
            elif command == "KNOB_RIGHT":
                macro_name = profile_data.get("knobs", {}).get("knob_rotate_right")
            elif command == "KNOB_PRESS":
                macro_name = profile_data.get("knobs", {}).get("knob_press")
            
            if macro_name:
                self._execute_macro_by_name(macro_name, profile_data)
    
    # --- New Feature Methods ---
    
    # Firmware Updates
    def link_app_to_profile(self, profile_name, app_exe):
        """Links an application executable to a profile for auto-switching."""
        try:
            if not app_exe:
                return {"status": "error", "message": "Application name cannot be empty"}
            
            # Update config rules
            rules = self._config.get("auto_switching", {}).get("rules", {})
            
            # Enforce lowercase for keys
            app_key = app_exe.lower()
            rules[app_key] = profile_name
            
            # Save config
            if "auto_switching" not in self._config:
                self._config["auto_switching"] = {"enabled": True, "rules": rules}
            else:
                self._config["auto_switching"]["rules"] = rules
                
            self._save_config()
            
            # Update service
            self._profile_switcher.update_config(self._config)
            
            return {"status": "success", "message": f"Linked {app_exe} to {profile_name}"}
        except Exception as e:
            logger.error(f"Error linking app: {e}")
            return {"status": "error", "message": str(e)}

    def get_linked_app(self, profile_name):
        """Returns the apps linked to the profile."""
        try:
            rules = self._config.get("auto_switching", {}).get("rules", {})
            linked_apps = [app for app, prof in rules.items() if prof == profile_name]
            return {"status": "success", "apps": linked_apps}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_active_processes(self):
        """Returns list of running applications with visible windows."""
        try:
            apps = self._profile_switcher.get_active_windows()
            return {"status": "success", "apps": apps}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def check_for_updates(self):
        """Check GitHub for both Firmware and App updates."""
        try:
            firmware_result = self._firmware_update_service.check_firmware_updates()
            # USE NEW UPDATE MANAGER for App Updates
            app_result = self._update_manager.check_app_update()
            
            return {
                "status": "success", 
                "firmware": firmware_result,
                "app": app_result
            }
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            return {"status": "error", "message": str(e)}

    def download_app_update(self, download_url):
        """Download app update using UpdateManager."""
        return self._update_manager.download_update(download_url)

    def trigger_app_restart(self):
        """Trigger non-blocking restart sequence."""
        return self._update_manager.trigger_restart()
    
    def download_firmware_update(self, download_url: str):
        """Download firmware update from GitHub."""
        try:
            save_path = APP_ROOT / "firmware" / "update.bin"
            success = self._firmware_update_service.download_firmware(download_url, save_path)
            
            if success:
                return {"status": "success", "path": str(save_path)}
            else:
                return {"status": "error", "message": "Download failed"}
        except Exception as e:
            logger.error(f"Error downloading firmware: {e}")
            return {"status": "error", "message": str(e)}
    
    # Community Library
    def get_community_categories(self):
        """Get list of community macro categories."""
        try:
            categories = self._community_library_service.get_categories()
            return {"status": "success", "categories": categories}
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_community_macros(self, category: str = None, search: str = None):
        """Get community macros by category or search query."""
        try:
            if search:
                macros = self._community_library_service.search_macros(search)
            elif category:
                macros = self._community_library_service.get_macros_in_category(category)
            else:
                macros = self._community_library_service.get_all_macros()
            
            return {"status": "success", "macros": macros}
        except Exception as e:
            logger.error(f"Error fetching macros: {e}")
            return {"status": "error", "message": str(e)}
    
    def install_community_macro(self, macro_data: Dict):
        """Install a community macro OR profile."""
        try:
            install_type = macro_data.get('type', 'macro')
            
            if install_type == 'profile':
                # --- PROFILE INSTALLATION ---
                profile_content = macro_data.get('profile', {})
                if not profile_content:
                    return {"status": "error", "message": "Invalid profile data"}
                
                # Mark as community origin
                profile_content['origin'] = 'community-profile'
                
                # Generate unique profile name
                base_name = macro_data.get('name', 'Community Profile')
                profile_name = base_name
                counter = 1
                
                while profile_name in self._profiles.get("profiles", {}):
                    profile_name = f"{base_name} ({counter})"
                    counter += 1
                
                # Check for existing keys to prevent overwriting if something is wrong (safety check)
                # But here we are creating a NEW profile, so it's safe.
                
                self._profiles["profiles"][profile_name] = profile_content
                
                # Optional: Switch to this new profile immediately?
                # For now just save it. The frontend might request a switch.
                self._profiles["active_profile"] = profile_name 
                self._current_profile_name = profile_name
                
                self._profile_service.save_profiles(self._profiles)
                self._profile_switcher.notify_manual_switch(profile_name) 
                
                logger.info(f"Installed community profile: {profile_name}")
                return {"status": "success", "name": profile_name, "type": "profile"}

            else:
                # --- MACRO INSTALLATION ---
                # Add origin field
                if 'macro' in macro_data:
                    macro_content = macro_data['macro']
                else:
                    macro_content = macro_data
                
                # Mark as community origin
                macro_content['origin'] = 'community'
                
                # Get current profile
                profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
                if 'macros' not in profile_data:
                    profile_data['macros'] = {}
                
                # Add macro with unique name
                macro_name = macro_data.get('name', 'Unnamed Macro')
                base_name = macro_name
                counter = 1
                
                while macro_name in profile_data['macros']:
                    macro_name = f"{base_name} ({counter})"
                    counter += 1
                
                profile_data['macros'][macro_name] = macro_content
                
                # Save
                self._profiles["profiles"][self._current_profile_name] = profile_data
                self._profile_service.save_profiles(self._profiles)
                
                logger.info(f"Installed community macro: {macro_name}")
                return {"status": "success", "name": macro_name, "type": "macro"}

        except Exception as e:
            logger.error(f"Error installing item: {e}")
            return {"status": "error", "message": str(e)}
    
    def submit_community_macro(self, macro_data: Dict):
        """Submit a macro directly to the GitHub community repo."""
        try:
            # Check for token first
            token = self._config.get('github', {}).get('token')
            if not token:
                return {"status": "error", "message": "GitHub Personal Access Token is missing in config.json"}

            result = self._community_library_service.upload_macro(macro_data)
            return result
        except Exception as e:
            logger.error(f"Error submitting macro: {e}")
            return {"status": "error", "message": str(e)}
    
    # --- Icon Methods ---
    def get_icon_categories(self):
        """Get list of icon categories (subdirectories)."""
        try:
            icons_dir = APP_ROOT / "app" / "assets" / "icons"
            if not icons_dir.exists():
                return {"status": "success", "categories": []}
            
            categories = [d.name for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            return {"status": "success", "categories": sorted(categories)}
        except Exception as e:
            logger.error(f"Error fetching icon categories: {e}")
            return {"status": "error", "message": str(e)}

    def get_icons(self, category):
        """Get icons in a category."""
        try:
            icons_dir = APP_ROOT / "app" / "assets" / "icons" / category
            if not icons_dir.exists():
                return {"status": "error", "message": "Category not found"}
            
            # Extensions to include
            valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
            
            icons = []
            for f in icons_dir.iterdir():
                if f.is_file() and f.suffix.lower() in valid_exts:
                    # Return relative path from assets for use in frontend
                    # Frontend path: icons/<category>/<filename>
                    icons.append(f"icons/{category}/{f.name}")
            
            return {"status": "success", "icons": sorted(icons)}
            return {"status": "success", "icons": sorted(icons)}
        except Exception as e:
            logger.error(f"Error fetching icons: {e}")
            return {"status": "error", "message": str(e)}

    def _ensure_icon_cache(self):
        """Load icons from disk into memory if not already loaded."""
        if self._icon_cache is not None:
            return

        try:
            icons_dir = APP_ROOT / "app" / "assets" / "icons"
            if not icons_dir.exists():
                self._icon_cache = {}
                return
            
            data = {}
            valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
            
            # Sort categories
            categories = sorted([d for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
            
            for category_dir in categories:
                cat_name = category_dir.name
                icons = []
                for f in category_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        icons.append(f"icons/{cat_name}/{f.name}")
                if icons:
                    data[cat_name] = sorted(icons)
            
            self._icon_cache = data
            logger.info("Icon cache built successfully")
        except Exception as e:
            logger.error(f"Error building icon cache: {e}")
            self._icon_cache = {}

    def get_all_icons_grouped(self):
        """Get all icons grouped by category (Cached)."""
        try:
            self._ensure_icon_cache()
            return {"status": "success", "data": self._icon_cache}
        except Exception as e:
            logger.error(f"Error fetching grouped icons: {e}")
            return {"status": "error", "message": str(e)}

    def search_icons(self, query):
        """Search for icons across all categories (Cached)."""
        try:
            self._ensure_icon_cache()
            query = query.lower()
            matches = []
            
            for category, icons in self._icon_cache.items():
                for icon_path in icons:
                    # icon_path is like "icons/Category/icon.svg"
                    filename = icon_path.split('/')[-1].lower()
                    if query in filename:
                        matches.append(icon_path)
            
            return {"status": "success", "icons": sorted(matches)}
        except Exception as e:
            logger.error(f"Error searching icons: {e}")
            return {"status": "error", "message": str(e)}
    
    # Auto-Switching
    def get_auto_switch_status(self):
        """Get auto-switching status and rules."""
        try:
            config = self._config.get('auto_switching', {})
            return {
                "status": "success",
                "enabled": config.get('enabled', False),
                "rules": config.get('rules', {})
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def set_auto_switch_enabled(self, enabled: bool):
        """Enable or disable auto-switching."""
        try:
            if 'auto_switching' not in self._config:
                self._config['auto_switching'] = {}
            
            self._config['auto_switching']['enabled'] = enabled
            self._save_config()
            
            # Start or stop the service
            if enabled:
                self._profile_switcher.set_enabled(True)
                if not self._profile_switcher.monitoring_thread or not self._profile_switcher.monitoring_thread.is_alive():
                    self._profile_switcher.start()
            else:
                self._profile_switcher.set_enabled(False)
            
            logger.info(f"Auto-switching {'enabled' if enabled else 'disabled'}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error setting auto-switch: {e}")
            return {"status": "error", "message": str(e)}
    
    def add_auto_switch_rule(self, process_name: str, profile_name: str):
        """Add an auto-switching rule."""
        try:
            if 'auto_switching' not in self._config:
                self._config['auto_switching'] = {'enabled': False, 'rules': {}}
            
            if 'rules' not in self._config['auto_switching']:
                self._config['auto_switching']['rules'] = {}
            
            self._config['auto_switching']['rules'][process_name] = profile_name
            self._save_config()
            
            # Update the service
            self._profile_switcher.add_rule(process_name, profile_name)
            
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error adding rule: {e}")
            return {"status": "error", "message": str(e)}
    
    def remove_auto_switch_rule(self, process_name: str):
        """Remove an auto-switching rule."""
        try:
            if process_name in self._config.get('auto_switching', {}).get('rules', {}):
                del self._config['auto_switching']['rules'][process_name]
                self._save_config()
                self._profile_switcher.remove_rule(process_name)
                return {"status": "success"}
            else:
                return {"status": "error", "message": "Rule not found"}
        except Exception as e:
            logger.error(f"Error removing rule: {e}")
            return {"status": "error", "message": str(e)}
    
    # Crash Reporting
            
            # Create issue title and body
            title = "[Crash Report] Application Error"
            body = f"""### Crash Report

**Time:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Version:** {self.firmware_version}

### Error Log
```
{error_log}
```

---
*Auto-generated crash report*
"""
            
            base_url = f"https://github.com/{repo}/issues/new"
            params = {
                'title': title,
                'body': body,
                'labels': 'bug,crash-report'
            }
            
            url = f"{base_url}?{urllib.parse.urlencode(params)}"
            
            # Open in browser
            import webbrowser
            webbrowser.open(url)
            
            return {"status": "success", "url": url}
        except Exception as e:
            logger.error(f"Error generating crash report URL: {e}")
            return {"status": "error", "message": str(e)}

    def _execute_macro_by_name(self, macro_name, profile_data):
        # Check custom macros first
        custom_macros = profile_data.get("macros", {})
        if macro_name in custom_macros:
            self._macro_execution_service.execute_macro(custom_macros[macro_name])
        else:
            # Check system macros
            system_macros = self._get_system_macros()
            if macro_name in system_macros:
                self._macro_execution_service.execute_macro(system_macros[macro_name])

    def _get_system_macros(self):
        return {
            # Clipboard
            "Copy": {"name": "Copy", "sequence": ["Ctrl", "C"]},
            "Paste": {"name": "Paste", "sequence": ["Ctrl", "V"]},
            "Cut": {"name": "Cut", "sequence": ["Ctrl", "X"]},
            "Select All": {"name": "Select All", "sequence": ["Ctrl", "A"]},
            
            # Editing
            "Undo": {"name": "Undo", "sequence": ["Ctrl", "Z"]},
            "Redo": {"name": "Redo", "sequence": ["Ctrl", "Y"]},
            "Save": {"name": "Save", "sequence": ["Ctrl", "S"]},
            "Find": {"name": "Find", "sequence": ["Ctrl", "F"]},
            "Replace": {"name": "Replace", "sequence": ["Ctrl", "H"]},
            
            # Navigation (Browser/App)
            "New Tab": {"name": "New Tab", "sequence": ["Ctrl", "T"]},
            "Close Tab": {"name": "Close Tab", "sequence": ["Ctrl", "W"]},
            "Switch Tab": {"name": "Switch Tab", "sequence": ["Ctrl", "Tab"]},
            "Refresh": {"name": "Refresh", "sequence": ["F5"]},
            
            # Media Controls
            "Volume Up": {"name": "Volume Up", "sequence": ["VolUp"]},
            "Volume Down": {"name": "Volume Down", "sequence": ["VolDown"]},
            "Mute": {"name": "Mute", "sequence": ["volumemute"]},
            "Play/Pause": {"name": "Play/Pause", "sequence": ["media_play_pause"]},
            "Next Track": {"name": "Next Track", "sequence": ["media_next"]},
            "Previous Track": {"name": "Previous Track", "sequence": ["media_previous"]},
            
            # Kept for backward compatibility
            "Mute Mic": {"name": "Mute Mic", "sequence": ["Ctrl", "Shift", "M"]},
            "Media Play/Pause": {"name": "Media Play/Pause", "sequence": ["media_play_pause"]},
            "Media Next": {"name": "Media Next", "sequence": ["media_next"]},
            "Media Prev": {"name": "Media Prev", "sequence": ["media_previous"]},
        }
