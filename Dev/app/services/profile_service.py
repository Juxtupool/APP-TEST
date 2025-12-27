import json
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(self, file_path="profiles.json"):
        self.file_path = file_path

    def load_profiles(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    profiles = json.load(f)
                    logger.info("Profiles loaded successfully")
                    return profiles
            except json.JSONDecodeError as e:
                logger.error(f"Profile file corrupted: {e}")
                # Try to load backup
                backup_path = str(self.file_path) + ".backup"
                if os.path.exists(backup_path):
                    logger.info("Attempting to restore from backup")
                    try:
                        with open(backup_path, "r") as f:
                            return json.load(f)
                    except Exception:
                        pass
                return {"profiles": {"Default": self.get_default_profile()}}
            except Exception as e:
                logger.error(f"Error loading profiles: {e}")
                return {"profiles": {"Default": self.get_default_profile()}}
        else:
            logger.info("No profile file found, using defaults")
            return {"profiles": {"Default": self.get_default_profile()}}

    def save_profiles(self, profiles):
        """Save profiles with automatic backup."""
        try:
            # Convert Path to string for concatenation
            file_path_str = str(self.file_path)
            
            # Create backup if file exists
            if os.path.exists(file_path_str):
                backup_path = file_path_str + ".backup"
                shutil.copy2(file_path_str, backup_path)
                logger.debug("Profile backup created")
            
            # Write to temporary file first
            temp_path = file_path_str + ".tmp"
            with open(temp_path, "w") as f:
                json.dump(profiles, f, indent=4)
            
            # Atomic replace
            if os.path.exists(file_path_str):
                os.remove(file_path_str)
            os.rename(temp_path, file_path_str)
            
            logger.info("Profiles saved successfully")
        except Exception as e:
            logger.error(f"Error saving profiles: {e}")
            raise

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
            "macros": {
                "Copy": ["Ctrl", "C"],
                "Paste": ["Ctrl", "V"],
            },
            "keys": {
                "0": "Copy",
                "1": "Paste",
            },
            "knobs": {}
        }
