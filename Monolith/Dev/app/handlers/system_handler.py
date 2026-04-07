import logging
import winreg
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

class SystemMixin:
    def window_minimize(self):
        """Minimize the window."""
        if self._window:
            self._window.minimize()
            
    def window_close(self):
        """Close the window (or hide if tray is enabled)."""
        if self._window:
            if self.tray_enabled:
                 self._window.hide()
            else:
                 self._window.destroy()

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
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}" --minimized'
                else:
                    current_dir = Path(__file__).parent.parent
                    main_script = current_dir / "main.py"
                    cmd = f'"{sys.executable}" "{main_script}" --minimized'
                
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

    def get_auto_switch_status(self):
        enabled = self._config.get("auto_switching", {}).get("enabled", True)
        return {"status": "success", "enabled": enabled}

    def set_auto_switch_enabled(self, enabled):
        if "auto_switching" not in self._config:
            self._config["auto_switching"] = {}
        self._config["auto_switching"]["enabled"] = enabled
        self._save_config()
        self._profile_switcher.update_config(self._config)
        return {"status": "success"}

    def get_tray_status(self):
        return {"status": "success", "enabled": self.tray_enabled}

    def set_tray_status(self, enabled):
        self.tray_enabled = enabled
        self._profiles["minimize_to_tray"] = enabled
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    def get_theme(self):
        return {"status": "success", "theme": self.current_theme}
    
    def set_theme(self, theme):
        # Deprecated but kept for compatibility, defaulting to dark
        self.current_theme = "dark" 
        self._profiles["theme"] = "dark"
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    def get_accent_color(self):
        return {"status": "success", "accent_color": self.current_accent_color}

    def set_accent_color(self, color):
        self.current_accent_color = color
        self._profiles["accent_color"] = color
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    def get_saved_colors(self):
        saved = self._profiles.get("saved_colors", [])
        return {"status": "success", "colors": saved}

    def add_saved_color(self, color):
        saved = self._profiles.get("saved_colors", [])
        if color not in saved:
            saved.append(color)
            self._profiles["saved_colors"] = saved
            self._profile_service.save_profiles(self._profiles)
        return {"status": "success", "colors": saved}

    def remove_saved_color(self, color):
        saved = self._profiles.get("saved_colors", [])
        if color in saved:
            saved.remove(color)
            self._profiles["saved_colors"] = saved
            self._profile_service.save_profiles(self._profiles)
        return {"status": "success", "colors": saved}
