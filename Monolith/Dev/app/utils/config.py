"""
Configuration loader for Overcontrol application.
Centralizes all configuration values with defaults.
Supports environment variables for sensitive data.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "app": {
        "log_level": "INFO",
        "log_file": "overcontrol.log"
    },
    "serial": {
        "baudrate": 115200,
        "timeout": 0.1,
        "port_cache_duration": 2.0
    },
    "firmware": {
        "flash_baudrate": 460800,
        "default_firmware_path": "firmware/build"
    },
    "knob": {
        "app_switcher_release_delay": 0.35
    },
    "debounce": {
        "serial_read_sleep": 0.01
    }
}


class Config:
    """Configuration manager with defaults and file loading."""
    
    def __init__(self, config_path="config.json"):
        self.config_path = Path(config_path)
        self.config = DEFAULT_CONFIG.copy()
        self._load_env_file()  # Load .env file first
        self.load()
    
    def _load_env_file(self):
        """Load environment variables from .env file if it exists."""
        env_path = Path('.env')
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
                logger.info("Environment variables loaded from .env")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")
    
    def load(self):
        """Load configuration from file, falling back to defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    # Deep merge with defaults
                    self._merge_config(self.config, user_config)
                    logger.info(f"Configuration loaded from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config, using defaults: {e}")
        else:
            logger.info("No config file found, using defaults")
    
    def _merge_config(self, base, update):
        """Recursively merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, path, default=None):
        """
        Get configuration value using dot notation.
        Example: config.get('serial.baudrate')
        
        Special handling for sensitive values:
        - 'github.token' checks GITHUB_TOKEN environment variable first
        """
        # Check for environment variable overrides for sensitive data
        if path == 'github.token':
            env_token = os.getenv('GITHUB_TOKEN', '').strip()
            if env_token:
                return env_token
        
        keys = path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


# Global config instance
_config = None


def get_config():
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
