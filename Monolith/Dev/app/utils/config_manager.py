import os
import json
import sys
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

def load_env_file(exe_dir: Path):
    """Load environment variables from .env file next to executable or CWD."""
    env_paths = []
    if getattr(sys, 'frozen', False):
        env_paths.append(exe_dir / ".env")
    env_paths.append(Path(".env"))
    
    for env_path in env_paths:
        if not env_path.exists():
            continue
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
            logger.info(f"Loaded environment variables from {env_path}")
            return  # Stop checking once we successfully load a .env file
        except Exception as e:
            logger.error(f"Failed to load environment file {env_path}: {e}")

def load_config(config_path: Path, exe_dir: Path) -> Dict:
    """Load configuration from config.json and merge environment GITHUB_TOKEN."""
    load_env_file(exe_dir)
    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}")
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Merge GITHUB_TOKEN environment variable into config dictionary
        env_token = os.getenv('GITHUB_TOKEN', '').strip()
        if env_token:
            if 'github' not in config:
                config['github'] = {}
            config['github']['token'] = env_token
            logger.info("GitHub token loaded from environment/env file")
            
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def save_config(config_path: Path, config: Dict):
    """Save configuration to config.json."""
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        logger.info(f"Configuration saved successfully to {config_path}")
    except Exception as e:
        logger.error(f"Error saving config to {config_path}: {e}")
