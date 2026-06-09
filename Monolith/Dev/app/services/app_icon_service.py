from app.core import BaseService, safe_api
import os
import base64
from typing import Optional, Dict
import win32api
import win32con
import win32gui
import win32ui
from PIL import Image
import io
import ctypes
from ctypes import wintypes

class AppIconService(BaseService):
    """
    Service for extracting application icons from Windows executables.
    Converts icons to base64-encoded data URIs for embedding in HTML.
    """
    
    def __init__(self):
        super().__init__()
        self._icon_cache: Dict[str, str] = {}
        self.logger.info("AppIconService initialized")
    
    @safe_api
    def get_app_icon(self, app_name: str, size: int = 32) -> Optional[str]:
        """
        Extract icon from a Windows application and return as base64 data URI.
        
        Args:
            app_name: Process name (e.g., 'chrome.exe', 'notepad.exe')
            size: Icon size in pixels (default 32x32)
            
        Returns:
            Base64-encoded data URI string, or None if extraction fails
        """
        cache_key = f"{app_name}_{size}"
        
        # Check cache first
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        # Find the full path to the executable
        exe_path = self._find_executable_path(app_name)
        if not exe_path:
            self.logger.warning(f"Could not find executable path for: {app_name}")
            return None
        
        # Extract icon as base64 data URI
        icon_data = self._extract_icon_to_base64(exe_path, size)
        
        if icon_data:
            self._icon_cache[cache_key] = icon_data
            return icon_data
        
        return None
    
    def _find_executable_path(self, app_name: str) -> Optional[str]:
        """
        Find the full path to an executable by process name.
        """
        try:
            # First, try to find it in running processes
            import psutil
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == app_name.lower():
                        if proc.info['exe'] and os.path.exists(proc.info['exe']):
                            self.logger.info(f"Found {app_name} in running processes: {proc.info['exe']}")
                            return proc.info['exe']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Known application paths for common apps
            app_name_lower = app_name.lower()
            known_paths = self._get_known_app_paths(app_name_lower)
            
            for path in known_paths:
                if os.path.exists(path):
                    self.logger.info(f"Found {app_name} in known location: {path}")
                    return path
            
            # Try common locations with targeted search (non-recursive first)
            search_dirs = [
                os.environ.get('ProgramFiles', 'C:\\Program Files'),
                os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs'),
                os.environ.get('APPDATA', ''),
            ]
            
            for base_dir in search_dirs:
                if not os.path.exists(base_dir):
                    continue
                    
                # Try direct subdirectories first (faster)
                try:
                    for item in os.listdir(base_dir):
                        item_path = os.path.join(base_dir, item)
                        if os.path.isdir(item_path):
                            exe_path = os.path.join(item_path, app_name)
                            if os.path.exists(exe_path):
                                self.logger.info(f"Found {app_name} in: {exe_path}")
                                return exe_path
                except (PermissionError, OSError):
                    continue
            
            # Try Windows directory
            windows_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', app_name)
            if os.path.exists(windows_path):
                self.logger.info(f"Found {app_name} in System32: {windows_path}")
                return windows_path
                
            self.logger.warning(f"Could not find executable for {app_name} after checking all locations")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding executable path for {app_name}: {e}")
            return None
    
    def _get_known_app_paths(self, app_name_lower: str) -> list:
        """Get known installation paths for common applications."""
        username = os.environ.get('USERNAME', '')
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        
        # Known paths for popular applications
        known_apps = {
            'spotify.exe': [
                os.path.join(appdata, 'Spotify', 'Spotify.exe'),
                os.path.join(localappdata, 'Microsoft', 'WindowsApps', 'Spotify.exe'),
            ],
            'chrome.exe': [
                'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                os.path.join(localappdata, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            ],
            'code.exe': [
                os.path.join(localappdata, 'Programs', 'Microsoft VS Code', 'Code.exe'),
                'C:\\Program Files\\Microsoft VS Code\\Code.exe',
            ],
            'resolve.exe': [
                'C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe',
                'C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Resolve.exe',
            ],
            'explorer.exe': [
                'C:\\Windows\\explorer.exe',
            ],
            'notepad.exe': [
                'C:\\Windows\\System32\\notepad.exe',
            ],
            'firefox.exe': [
                'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
                'C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe',
            ],
            'discord.exe': [
                os.path.join(localappdata, 'Discord', 'app-*', 'Discord.exe'),
            ],
            'slack.exe': [
                os.path.join(localappdata, 'slack', 'slack.exe'),
            ],
            'photoshop.exe': [
                'C:\\Program Files\\Adobe\\Adobe Photoshop 2024\\Photoshop.exe',
                'C:\\Program Files\\Adobe\\Adobe Photoshop 2023\\Photoshop.exe',
            ],
            'premiere.exe': [
                'C:\\Program Files\\Adobe\\Adobe Premiere Pro 2024\\Adobe Premiere Pro.exe',
                'C:\\Program Files\\Adobe\\Adobe Premiere Pro 2023\\Adobe Premiere Pro.exe',
            ],
            'obs64.exe': [
                'C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe',
            ],
            'blender.exe': [
                'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe',
                'C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe',
            ],
        }
        
        paths = known_apps.get(app_name_lower, [])
        
        # Expand wildcards
        expanded_paths = []
        for path in paths:
            if '*' in path:
                from glob import glob
                matches = glob(path)
                expanded_paths.extend(matches)
            else:
                expanded_paths.append(path)
        
        return expanded_paths
    
    def _extract_icon_to_base64(self, exe_path: str, size: int = 32) -> Optional[str]:
        """
        Extract icon from executable and convert to base64 data URI.
        """
        try:
            hicon = None
            
            # Method 1: Try Standard ExtractIconEx
            try:
                large, small = win32gui.ExtractIconEx(exe_path, 0)
                if large or small:
                    # Use the appropriate icon based on requested size
                    if size > 16 and large:
                        hicon = large[0]
                        # Clean up others
                        for icon in large[1:]: win32gui.DestroyIcon(icon)
                        for icon in small: win32gui.DestroyIcon(icon)
                    elif small:
                        hicon = small[0]
                        # Clean up others
                        for icon in large: win32gui.DestroyIcon(icon)
                        for icon in small[1:]: win32gui.DestroyIcon(icon)
                    else:
                        # Should not happen if large or small is True
                        if large: win32gui.DestroyIcon(large[0])
                        if small: win32gui.DestroyIcon(small[0])
                        
            except Exception as e:
                self.logger.debug(f"Standard extraction failed: {e}")
                
            # Method 2: Fallback to Shell API (SHGetFileInfo) if Method 1 failed
            if not hicon:
                try:
                    self.logger.info("Attempting Shell API fallback for icon extraction")
                    
                    _shell32 = ctypes.windll.shell32
                    
                    SHGFI_ICON = 0x000000100
                    SHGFI_LARGEICON = 0x000000000
                    SHGFI_SMALLICON = 0x000000001
                    
                    class SHFILEINFO(ctypes.Structure):
                        _fields_ = [
                            ("hIcon", wintypes.HICON),
                            ("iIcon", ctypes.c_int),
                            ("dwAttributes", wintypes.DWORD),
                            ("szDisplayName", wintypes.WCHAR * 260),
                            ("szTypeName", wintypes.WCHAR * 80)
                        ]
                    
                    shfileinfo = SHFILEINFO()
                    
                    flags = SHGFI_ICON
                    if size > 16:
                        flags |= SHGFI_LARGEICON
                    else:
                        flags |= SHGFI_SMALLICON

                    _shell32.SHGetFileInfoW(
                        exe_path,
                        0,
                        ctypes.byref(shfileinfo),
                        ctypes.sizeof(shfileinfo),
                        flags
                    )
                    
                    if shfileinfo.hIcon:
                        hicon = shfileinfo.hIcon
                except Exception as e:
                    self.logger.error(f"Shell fallback failed: {e}")

            if not hicon:
                self.logger.warning(f"Failed to extract any icon handle for {exe_path}")
                return None
            
            # Common Logic: Convert HICON to Base64 PNG
            hdc_handle = win32gui.GetDC(0)
            try:
                # Create a device context
                hdc = win32ui.CreateDCFromHandle(hdc_handle)
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, size, size)
                hdc_mem = hdc.CreateCompatibleDC()
                
                hdc_mem.SelectObject(hbmp)
                
                # Draw the icon
                win32gui.DrawIconEx(
                    hdc_mem.GetSafeHdc(),
                    0, 0,
                    hicon,
                    size, size,
                    0,
                    None,
                    win32con.DI_NORMAL
                )
                
                # Convert to PIL Image
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGBA',
                    (size, size),
                    bmpstr,
                    'raw',
                    'BGRA',
                    0,
                    1
                )

                # Check if alpha channel is valid (not all zeros)
                # If all zeros, it means the alpha wasn't captured correctly (likely appeared transparent black)
                # In that case, we force full opacity or fallback to RGB
                if img.getextrema()[3][1] == 0:
                     img = Image.frombuffer(
                        'RGB',
                        (size, size),
                        bmpstr,
                        'raw',
                        'BGRX',
                        0,
                        1
                    ).convert('RGBA')

                
                # Convert to PNG and encode as base64
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # Cleanup DC objects
                hdc_mem.DeleteDC()
                hdc.DeleteDC()
                
                return f"data:image/png;base64,{img_base64}"
                
            finally:
                win32gui.ReleaseDC(0, hdc_handle)
                # Always destroy the icon handle we created/got
                if hicon:
                    win32gui.DestroyIcon(hicon)
            
        except Exception as e:
            self.logger.error(f"Error extracting icon from {exe_path}: {e}")
            return None
    
    def clear_cache(self):
        """Clear the icon cache."""
        self._icon_cache.clear()
        self.logger.info("Icon cache cleared")
