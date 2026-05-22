from app.core import safe_api, ApiResponse
import json

class MacroMixin:
    @safe_api
    def execute_macro(self, macro_data):
        if macro_data.get("type") == "window_service":
            action = macro_data.get("action")
            if action == "minimize":
                self._window_control_service.minimize_windows()
            elif action == "restore_all":
                self._window_control_service.restore_windows()
            return ApiResponse.success()

        self._macro_execution_service.execute_macro(macro_data)
        return ApiResponse.success()

    @safe_api
    def start_macro_recording(self):
        """Start recording macros with system shortcut suppression."""
        # Ensure the service has the bridge if not already set (though Api sets it)
        if not self._macro_recording_service._ui_bridge and hasattr(self, '_ui_bridge'):
            self._macro_recording_service.set_ui_bridge(self._ui_bridge)
            
        self._macro_recording_service.start_recording()
        return ApiResponse.success()

    @safe_api
    def stop_macro_recording(self):
        """Stop macro recording."""
        self._macro_recording_service.stop_recording()
        return ApiResponse.success()

    def _execute_macro_by_name(self, macro_name, profile_data):
        """Helper to execute macro by name from profile data or system defaults."""
        # 1. Check custom macros in profile
        macro_data = profile_data.get("macros", {}).get(macro_name)
        if macro_data:
            self.execute_macro(macro_data)
        else:
            # 2. Check system macros fallback
            system_macros = self._get_system_macros()
            if macro_name in system_macros:
                self.execute_macro(system_macros[macro_name])
            else:
                self.logger.warning(f"Macro '{macro_name}' not found in profile or system defaults")

    def _get_system_macros(self):
        """Return the dictionary of built-in system macros."""
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
            # Navigation
            "New Tab": {"name": "New Tab", "sequence": ["Ctrl", "T"]},
            "Close Tab": {"name": "Close Tab", "sequence": ["Ctrl", "W"]},
            "Switch Tab": {"name": "Switch Tab", "sequence": ["Ctrl", "Tab"]},
            "Refresh": {"name": "Refresh", "sequence": ["F5"]},
            # Window Management
            "Minimize Window": {"name": "Minimize Window", "type": "window_service", "action": "minimize"},
            "Restore Windows": {"name": "Restore Windows", "type": "window_service", "action": "restore_all"},
            # Media
            "Volume Up": {"name": "Volume Up", "sequence": ["volup"]},
            "Volume Down": {"name": "Volume Down", "sequence": ["voldown"]},
            "Mute": {"name": "Mute", "sequence": ["volumemute"]},
            "Play/Pause": {"name": "Play/Pause", "sequence": ["media_play_pause"]},
            "Next Track": {"name": "Next Track", "sequence": ["media_next"]},
            "Previous Track": {"name": "Previous Track", "sequence": ["media_previous"]},
        }

    def _execute_knob_callback(self, command: str):
        """Execute knob callback with proper logging."""
        profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
        current_mode = self._knob_controller.mode
        self.logger.debug(f"Knob Callback - Command: {command}, Mode: {current_mode}")
        macro_name = None
        
        if current_mode == "Standard":
            if command == "KNOB_LEFT":
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["voldown"]})
            elif command == "KNOB_RIGHT":
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["volup"]})
            elif command == "KNOB_PRESS":
                self._macro_execution_service.execute_macro({"type": "key", "sequence": ["volumemute"]})
        
        elif current_mode in ["Custom", "Timeline Scrubber"]:
            if command == "KNOB_LEFT":
                macro_name = profile_data.get("knobs", {}).get("knob_rotate_left")
            elif command == "KNOB_RIGHT":
                macro_name = profile_data.get("knobs", {}).get("knob_rotate_right")
            elif command == "KNOB_PRESS":
                macro_name = profile_data.get("knobs", {}).get("knob_press")
            
            if macro_name:
                self._execute_macro_by_name(macro_name, profile_data)

    def _handle_serial_command(self, message: str):
        """Handle serial command with proper error handling."""
        try:
            if message in ["KNOB_LEFT", "KNOB_RIGHT", "KNOB_PRESS"]:
                # Apply knob direction reversal if enabled in config
                knob_config = self._config.get("knob", {})
                if knob_config.get("reverse_direction", False):
                    if message == "KNOB_LEFT":
                        message = "KNOB_RIGHT"
                    elif message == "KNOB_RIGHT":
                        message = "KNOB_LEFT"
                
                self._knob_controller.handle_input(message)
                return

            profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
            macro_name = None
            
            if message.startswith("KEY_") and message.endswith("_PRESSED"):
                try:
                    idx = int(message.split("_")[1])
                    self.logger.debug(f"Key {idx} pressed")
                except (ValueError, IndexError) as e:
                    self.logger.error(f"Invalid key message format: {message}")
                    return
                
                macro_name = profile_data.get("keys", {}).get(str(idx))
            
            if macro_name:
                self._execute_macro_by_name(macro_name, profile_data)
                        
        except Exception as e:
            self.logger.error(f"Error handling serial command '{message}': {e}", exc_info=True)
            
    @safe_api
    def link_app_to_profile(self, profile_name, app_exe):
        """Links an application executable to a profile for auto-switching."""
        if not app_exe:
            return ApiResponse.error("Application name cannot be empty")
        
        rules = self._config.get("auto_switching", {}).get("rules", {})
        app_key = app_exe.lower()
        rules[app_key] = profile_name
        
        if "auto_switching" not in self._config:
            self._config["auto_switching"] = {"enabled": True, "rules": rules}
        else:
            self._config["auto_switching"]["rules"] = rules
            
        self._save_config()
        self._profile_switcher.update_config(self._config)
        
        return ApiResponse.success(message=f"Linked {app_exe} to {profile_name}")

    @safe_api
    def get_linked_app(self, profile_name):
        """Returns the apps linked to the profile."""
        rules = self._config.get("auto_switching", {}).get("rules", {})
        linked_apps = [app for app, prof in rules.items() if prof == profile_name]
        return ApiResponse.success(data=linked_apps, message="Apps found") # Original returned {"apps": ...}, adjusting to data

    @safe_api
    def get_active_processes(self):
        """Returns list of running applications with visible windows."""
        apps = self._profile_switcher.get_active_windows()
        return ApiResponse.success(data=apps)

    @safe_api
    def unlink_app_from_profile(self, profile_name):
        """Unlinks all applications from a profile."""
        rules = self._config.get("auto_switching", {}).get("rules", {})
        # Find apps linked to this profile
        apps_to_remove = [app for app, prof in rules.items() if prof == profile_name]
        
        if not apps_to_remove:
            return ApiResponse.success(message="No apps linked to this profile")
        
        for app in apps_to_remove:
            del rules[app]
            
        self._save_config()
        self._profile_switcher.update_config(self._config)
        
        return ApiResponse.success(message=f"Unlinked {len(apps_to_remove)} apps")
