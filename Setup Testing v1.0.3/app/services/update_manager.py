import os
import sys
import json
import time
import requests
import subprocess
import threading
import logging
import shutil
import zipfile
from pathlib import Path
from packaging import version as pkg_version
from ..version import APP_VERSION

logger = logging.getLogger(__name__)

class UpdateManager:
    def __init__(self, config_manager=None):
        self._config_manager = config_manager
        # Determine app root
        if getattr(sys, 'frozen', False):
             self.app_root = Path(sys.executable).parent
        else:
             # V4_Webview_NodeMCU/Setup Files/app/services/ -> V4_Webview_NodeMCU/Setup Files/
             self.app_root = Path(__file__).parent.parent.parent

        self.temp_dir = self.app_root / "temp_update"
        self._restart_timer = None
        
        # Load config directly if manager not provided
        self.config = {}
        if config_manager and isinstance(config_manager, dict):
             self.config = config_manager
        elif config_manager:
            # Assume it's a ConfigManager object matching a certain interface
             pass # Logic to be added if needed, for now we pass dict or rely on api to pass config
    
    def set_config(self, config):
        self.config = config

    def check_app_update(self):
        """Check GitHub for app updates."""
        try:
            repo = self.config.get('github', {}).get('app_repo', '')
            if not repo:
                 return {'status': 'error', 'message': 'App repository not configured'}
            
            current_version = APP_VERSION
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            
            headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Macropad-Pro'}
            token = self.config.get('github', {}).get('token')
            if token:
                headers['Authorization'] = f'token {token}'
            
            logger.info(f"Checking for app updates at {api_url}")
            resp = requests.get(api_url, headers=headers, timeout=10)
            
            if resp.status_code != 200:
                 return {'status': 'error', 'message': f'GitHub API error: {resp.status_code}'}
            
            data = resp.json()
            latest_version_str = data.get('tag_name', '0.0.0').lstrip('v')
            
            # Version comparison
            try:
                is_newer = pkg_version.parse(latest_version_str) > pkg_version.parse(current_version)
            except:
                is_newer = latest_version_str != current_version
            
            # Find asset
            download_url = None
            asset_name = None
            
            # Priority: 
            # 1. Target extension (.zip as requested)
            # 2. .exe (backup)
            # 3. Source code zipball (fallback)
            
            preferred_ext = '.zip'
            backup_ext = '.exe'


            # Helper to find asset by extension
            def find_asset(ext):
                for a in data.get('assets', []):
                    if a.get('name', '').endswith(ext):
                        return a
                return None

            asset = find_asset(preferred_ext)
            if not asset and preferred_ext != backup_ext:
                asset = find_asset(backup_ext)
            
            if asset:
                 download_url = asset.get('browser_download_url')
                 asset_name = asset.get('name')
            
            # Fallback to source code REMOVED. 
            # We strictly require a compiled asset (.zip or .exe) for an app update.
            # if not download_url:
            #      download_url = data.get('zipball_url')
            #      asset_name = "source_code.zip"

            return {
                'status': 'success',
                'update_available': is_newer and (download_url is not None),
                'current_version': current_version,
                'latest_version': latest_version_str,
                'download_url': download_url,
                'release_notes': data.get('body', ''),
                'html_url': data.get('html_url', '')
            }

        except Exception as e:
            logger.error(f"Error checking app update: {e}")
            return {'status': 'error', 'message': str(e)}

    def download_update(self, url):
        """Download update to temp directory."""
        try:
            if not url:
                return {'status': 'error', 'message': 'No download URL provided'}
            
            # Clean temp dir
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            
            filename = "update_package" + (".exe" if url.endswith(".exe") else ".zip")
            save_path = self.temp_dir / filename
            
            logger.info(f"Downloading update from {url} to {save_path}")
            
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            # If it's a zip (Dev mode or Source), extract it
            if filename.endswith(".zip"):
                 with zipfile.ZipFile(save_path, 'r') as zip_ref:
                      zip_ref.extractall(self.temp_dir)
                 
                 # cleanup zip
                 os.remove(save_path)

                 # --- Handle Nested Folders (GitHub Zip Behavior) ---
                 # Check if the extracted directory contains only one folder
                 contents = [c for c in self.temp_dir.iterdir() if not c.name.startswith('.')]
                 if len(contents) == 1 and contents[0].is_dir():
                     logger.info(f"Unwrapping nested folder: {contents[0].name}")
                     # Move everything inside this folder up to temp_dir
                     for item in contents[0].iterdir():
                         shutil.move(str(item), str(self.temp_dir))
                     # Remove the now empty nested folder
                     contents[0].rmdir()
                 
                 # Post-processing for Dev Mode: Delete 'app/assets' from update
                 # to prevent overwriting local UI changes
                 if not getattr(sys, 'frozen', False):
                      self._cleanup_dev_update()
            
            return {'status': 'success'}

        except Exception as e:
            logger.error(f"Download error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _cleanup_dev_update(self):
        """Remove assets from update in Dev mode to preserve local changes."""
        logger.info("Dev Mode: Cleaning up update assets to preserve local UI")
        # Structure might be: temp/Repo-Name/Setup Files/app/assets
        # We need to find where 'app' is.
        for root, dirs, files in os.walk(self.temp_dir):
             if 'app' in dirs:
                  app_dir = Path(root) / 'app'
                  assets_dir = app_dir / 'assets'
                  if assets_dir.exists():
                       try:
                           shutil.rmtree(assets_dir)
                           logger.info("Removed assets from update package")
                       except Exception as e:
                           logger.warning(f"Failed to remove assets: {e}")
                  break

    def trigger_restart(self):
        """
        Non-blocking restart trigger.
        Returns immediately to frontend, then kills app after delay.
        """
        logger.info("Triggering restart sequence in 0.5s...")
        
        # Start background timer
        self._restart_timer = threading.Timer(0.5, self._restart_sequence)
        self._restart_timer.start()
        
        return {'status': 'success', 'message': 'Restarting...'}

    def _restart_sequence(self):
        """Actual restart logic running in background thread."""
        try:
            logger.info("Starting restart sequence...")
            
            # 1. Generate Batch Script
            batch_script = self.app_root / "update_installer.bat"
            
            # Determine logic based on Freeze (Prod) vs Dev
            is_frozen = getattr(sys, 'frozen', False)
            
            # Source: content of temp_dir
            # Target: self.app_root
            
            # Bat script logic:
            # 1. Wait for PID to die (timeout loop)
            # 2. Xcopy /y temp_dir/* app_root/*
            # 3. Start app
            
            current_pid = os.getpid()
            
            # Force kill the current process in the batch script to ensure clean restart
            # command: taskkill /PID {pid} /F
            
            if is_frozen:
                executable = sys.executable
            else:
                executable = f'"{sys.executable}" "{self.app_root / "run.py"}"'
            
            # Common wait/kill logic for the batch script
            kill_cmd = f'taskkill /PID {current_pid} /F'
            
            # Robocopy is robust but xcopy is simpler for single batch file
            # We need to handle moving files from the extracted folder (GitHub zips usually have a root folder)
            
            script_content = f"""
@echo off
title Updating Macropad Pro...
color 0b

echo Waiting for application to close (PID: {current_pid})...
timeout /t 2 /nobreak >nul
{kill_cmd} >nul 2>&1

echo Install started...

:: Source directory (where we extracted)
set "SOURCE={self.temp_dir}"
:: Destination
set "DEST={self.app_root}"

echo Source: %SOURCE%
echo Dest: %DEST%

:: Move files
:: Note: In dev mode, we need to be careful. In prod, we just overwrite.
:: GitHub zip extracts to a subfolder usually. We need to find it.
:: For now, we assume UpdateManager flattened it or we copy everything from temp

xcopy "%SOURCE%\\*" "%DEST%\\" /E /H /Y /C /I

echo Update applied.
echo Cleaning up...
rmdir /s /q "%SOURCE%"

echo Restarting application...
start "" {executable}

:: Self-delete script ?? Maybe not needed, good for debug
:: (goto) 2>nul & del "%~f0"
exit
"""
            with open(batch_script, "w") as f:
                f.write(script_content)
            
            logger.info(f"Batch script generated at {batch_script}")
            
            # 2. Launch Batch Script (Detached)
            subprocess.Popen([str(batch_script)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # 3. Kill Self
            logger.info("Goodbye!")
            os._exit(0) # Hard exit to prevent any hooks from stalling
            
        except Exception as e:
            logger.error(f"Restart sequence failed: {e}")
