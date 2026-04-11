import requests
import logging
from pathlib import Path
from typing import Dict, Optional
from packaging import version as pkg_version

logger = logging.getLogger(__name__)


class FirmwareUpdateService:
    """
    Checks GitHub releases for firmware updates and downloads them.
    Uses GitHub API (no server needed).
    """
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Dictionary with github.firmware_repo, github.app_repo and current versions
        """
        self.firmware_repo = config.get('github', {}).get('firmware_repo', '')
        self.app_repo = config.get('github', {}).get('app_repo', '')
        
        self.current_firmware_version = config.get('firmware', {}).get('current_version', '0.0.0')
        self.current_app_version = config.get('app', {}).get('current_version', '1.0.0')
        
        self.github_token = config.get('github', {}).get('token', None)
        
        logger.info(f"UpdateService initialized. FW: {self.current_firmware_version}, App: {self.current_app_version}")

    def _get_api_url(self, repo: str) -> Optional[str]:
        if not repo:
            return None
        return f"https://api.github.com/repos/{repo}/releases/latest"

    
    def _get_headers(self) -> Dict:
        """Get headers for GitHub API request."""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Overcontrol'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
            logger.debug("Requesting with Authentication")
        else:
            logger.debug("Requesting Unauthenticated (Public Access)")
        
        return headers
    
    def _check_updates_generic(self, repo: str, current_version: str, asset_extension: str = '.bin') -> Dict:
        """Generic update checker."""
        api_url = self._get_api_url(repo)
        if not api_url:
            return {'error': 'Repository not configured'}
            
        # If we don't know the current version, assume up to date (or user should connect device)
        # preventing false "Update Available" messages when disconnected.
        if current_version == "Unknown":
            return {'update_available': False, 'current_version': 'Unknown (Connect Device)', 'latest_version': 'Unknown'}
        
        try:
            logger.info(f"Checking for updates at {api_url}")
            response = requests.get(api_url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 404:
                return {'error': 'Repository not found or no releases available'}
            
            if response.status_code == 403:
                return {'error': 'GitHub API Rate Limit Exceeded (Wait 60 mins or add token)'}
            
            if response.status_code != 200:
                return {'error': f'GitHub API returned status {response.status_code}'}
            
            release_data = response.json()
            latest_version_str = release_data.get('tag_name', '0.0.0').lstrip('v')
            
            # Find asset
            download_url = None
            asset_name = None
            asset_size = 0
            
            for asset in release_data.get('assets', []):
                name = asset.get('name', '')
                if name.endswith(asset_extension):
                    download_url = asset.get('browser_download_url')
                    asset_name = name
                    asset_size = asset.get('size', 0)
                    break
            
            # For App updates, we might not need a specific asset if we just want to notify
            if not download_url and asset_extension == '.bin':
                 return {'error': 'No firmware binary (.bin) found in latest release'}

            # Compare versions
            try:
                is_newer = pkg_version.parse(latest_version_str) > pkg_version.parse(current_version)
            except Exception as e:
                logger.warning(f"Version comparison failed: {e}. Comparing as strings.")
                is_newer = latest_version_str != current_version
            
            result = {
                'update_available': is_newer,
                'latest_version': latest_version_str,
                'current_version': current_version,
                'download_url': download_url,
                'release_notes': release_data.get('body', 'No release notes available'),
                'published_at': release_data.get('published_at', ''),
                'asset_name': asset_name,
                'asset_size': asset_size,
                'html_url': release_data.get('html_url', '')
            }
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error checking for updates: {e}")
            return {'error': f'Network error: {str(e)}'}
        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}")
            return {'error': f'Unexpected error: {str(e)}'}

    def check_firmware_updates(self, current_version: str = None) -> Dict:
        """Check for firmware updates."""
        # Use passed version if valid. If None, fallback to config.
        # Ensure we keep "Unknown" if passed, to avoid falling back to stale config "1.0.0"
        ver = current_version if current_version is not None else self.current_firmware_version
        return self._check_updates_generic(self.firmware_repo, ver, '.bin')

    def check_app_updates(self) -> Dict:
        """Check for app updates."""
        # For app, we accept zip or exe, or just link to release page
        return self._check_updates_generic(self.app_repo, self.current_app_version, '')
    
    def download_firmware(self, download_url: str, save_path: Path) -> bool:
        """
        Download firmware from GitHub.
        
        Args:
            download_url: Direct URL to firmware binary
            save_path: Local path to save the file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading firmware from {download_url}")
            
            # Ensure parent directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Stream download for large files
            response = requests.get(download_url, headers=self._get_headers(), stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress every 100KB
                        if downloaded % 102400 == 0 and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"Download progress: {progress:.1f}%")
            
            logger.info(f"Firmware downloaded successfully to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading firmware: {e}")
            return False
    
    def set_current_version(self, version: str):
        """Update the current firmware version."""
        self.current_version = version
        logger.info(f"Current firmware version set to {version}")
