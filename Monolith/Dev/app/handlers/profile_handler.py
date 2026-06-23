from app.core import safe_api, ApiResponse

class ProfileMixin:
    @safe_api
    def get_profiles(self):
        self._profiles = self._profile_service.load_profiles()
        
        # Add linked app information to each profile
        rules = self._config.get("auto_switching", {}).get("rules", {})
        profiles_data = self._profiles.get("profiles", {})
        
        for profile_name in profiles_data:
            # Find apps linked to this profile
            linked_apps = [app for app, prof in rules.items() if prof == profile_name]
            profiles_data[profile_name]["linked_apps"] = linked_apps
        
        return self._profiles

    @safe_api
    def save_profiles(self, profiles):
        """Save profiles with validation, preserving global settings."""
        if not isinstance(profiles, dict):
            self.logger.error(f"Invalid profiles type: {type(profiles)}")
            return ApiResponse.error("Invalid profiles format")
        
        # FIX: Merge incoming profiles data with existing state to preserve global settings
        # (accent_color, tray settings, etc.) which might not be sent by frontend
        if "profiles" in profiles:
            self._profiles["profiles"] = profiles["profiles"]
            
        # Optional: update active_profile if sent (though usually set via set_active_profile)
        if "active_profile" in profiles:
             self._profiles["active_profile"] = profiles["active_profile"]
             
        # Ensure active_profile is preserved if missing from both
        if "active_profile" not in self._profiles:
             self._profiles["active_profile"] = self._current_profile_name
        
        self._profile_service.save_profiles(self._profiles)
        self.logger.info("Profiles saved successfully (merged)")
        return ApiResponse.success()

    @safe_api
    def set_active_profile(self, profile_name: str, is_auto: bool = False):
        """Set active profile with validation."""
        if not isinstance(profile_name, str) or not profile_name:
            self.logger.error("Invalid profile name")
            return ApiResponse.error("Invalid profile name")
        
        # Validate profile exists
        if profile_name not in self._profiles.get("profiles", {}):
            self.logger.error(f"Profile not found: {profile_name}")
            return ApiResponse.error("Profile not found")
        
        self._current_profile_name = profile_name
        
        # Notify switcher if manual
        if not is_auto and self._profile_switcher:
             self._profile_switcher.notify_manual_switch(profile_name)
             
        self.logger.info(f"Active profile set to: {profile_name} (Auto: {is_auto})")
        
        # Save active profile setting
        self._profiles["active_profile"] = profile_name
        self._profile_service.save_profiles(self._profiles)
        
        # Set Knob Mode
        profile_data = self._profiles.get("profiles", {}).get(profile_name, {})
        knob_mode = profile_data.get("knob_mode", "Standard")
        knob_speed = profile_data.get("knob_speed", 1)
        self._knob_controller.set_mode(knob_mode)
        self._knob_controller.set_speed(knob_speed)
        
        # Send active knob mode to hardware
        if hasattr(self, '_serial_service') and self._serial_service.is_connected:
            self._serial_service.send_raw_command(f"SET_KNOB_MODE {knob_mode}")
        
        return ApiResponse.success()

    @safe_api
    def set_knob_mode(self, mode):
        # Update current profile
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_mode"] = mode
            self._profile_service.save_profiles(self._profiles)
            
        self._knob_controller.set_mode(mode)
        
        # Send changed knob mode to hardware
        if hasattr(self, '_serial_service') and self._serial_service.is_connected:
            self._serial_service.send_raw_command(f"SET_KNOB_MODE {mode}")
            
        return ApiResponse.success()

    @safe_api
    def set_knob_speed(self, speed):
        # Update current profile
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_speed"] = speed
            self._profile_service.save_profiles(self._profiles)
            
        self._knob_controller.set_speed(speed)
        return ApiResponse.success()

    @safe_api
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
        self._knob_controller.set_mode("Standard")
        self._knob_controller.set_speed(1)
        
        # Send reset knob mode to hardware
        if hasattr(self, '_serial_service') and self._serial_service.is_connected:
            self._serial_service.send_raw_command("SET_KNOB_MODE Standard")
        
        # Reload UI using bridge
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.location.reload()")
        
        self.logger.info("Reset to defaults completed")
        return ApiResponse.success()
