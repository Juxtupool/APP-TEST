from app.core import BaseService
import json
import os
import shutil
import threading
from datetime import datetime

class ProfileService(BaseService):
    def __init__(self, file_path="profiles.json"):
        super().__init__()
        self.file_path = file_path
        self._lock = threading.Lock()

    def load_profiles(self):
        with self._lock:
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, "r") as f:
                        profiles = json.load(f)
                        self.logger.info("Profiles loaded successfully")
                        return profiles
                except json.JSONDecodeError as e:
                    self.logger.error(f"Profile file corrupted: {e}")
                    # Try to load backup
                    backup_path = str(self.file_path) + ".backup"
                    if os.path.exists(backup_path):
                        self.logger.info("Attempting to restore from backup")
                        try:
                            with open(backup_path, "r") as f:
                                return json.load(f)
                        except Exception:
                            pass
                    return {"profiles": {"Default": self.get_default_profile()}}
                except Exception as e:
                    self.logger.error(f"Error loading profiles: {e}")
                    return {"profiles": {"Default": self.get_default_profile()}}
            else:
                self.logger.info("No profile file found, using defaults")
                return {"profiles": {"Default": self.get_default_profile()}}

    def save_profiles(self, profiles):
        """Save profiles with automatic backup and retry logic."""
        with self._lock:
            try:
                # Convert Path to string for concatenation
                file_path_str = str(self.file_path)
                
                # Create backup if file exists
                if os.path.exists(file_path_str):
                    backup_path = file_path_str + ".backup"
                    try:
                        shutil.copy2(file_path_str, backup_path)
                        self.logger.debug("Profile backup created")
                    except OSError:
                         self.logger.warning("Failed to create backup")
                
                # Write to temporary file first
                temp_path = file_path_str + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(profiles, f, indent=4)
                
                # Robust replace with retries
                max_retries = 5
                for i in range(max_retries):
                    try:
                        if os.path.exists(file_path_str):
                            os.replace(temp_path, file_path_str)
                        else:
                            os.rename(temp_path, file_path_str)
                        break
                    except OSError as e:
                        # WinError 32: The process cannot access the file because it is being used by another process
                        if e.winerror == 32 and i < max_retries - 1:
                            import time
                            time.sleep(0.1)
                            continue
                        raise
                
                self.logger.info("Profiles saved successfully")
                return {"status": "success", "message": "Profiles saved"}
            except Exception as e:
                self.logger.error(f"Error saving profiles: {e}")
                return {"status": "error", "message": str(e)}

    def export_profile(self, profile_name, data, file_path):
        export_data = {
            "name": profile_name,
            "data": data
        }
        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=4)

    def import_profile(self, file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data.get("name"), data.get("data")
        except (json.JSONDecodeError, KeyError):
            return None, None

    def get_default_profile(self):
        return {
            "macros": {},
            "keys": {},
            "knobs": {}
        }
