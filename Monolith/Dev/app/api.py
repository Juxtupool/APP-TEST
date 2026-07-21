import os
import sys
import json
import time
import shutil
import logging
from logging.handlers import RotatingFileHandler
import threading
import queue
import base64
import io
import hashlib
import re
import functools
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import win32api
import win32con
import win32gui
import win32ui
from PIL import Image
from packaging import version as pkg_version
import psutil
import webview
import winreg

# Import our custom simplified components
from .serial_manager import SerialService, FlasherService
from .macro_manager import (
    MacroExecutionService,
    MacroRecordingService,
    KnobController,
    WindowControlService,
    ProfileSwitcherService
)
from .version import APP_VERSION

logger = logging.getLogger(__name__)

# Configure logging path
log_dir = Path(os.getenv('APPDATA')) / "Overcontrol"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "overcontrol.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

APP_ROOT = Path(__file__).parent.parent

if getattr(sys, 'frozen', False):
    EXE_DIR = Path(sys.executable).parent
    
    profile_target = EXE_DIR / "profiles.json"
    if not profile_target.exists():
        profile_source = APP_ROOT / "profiles.json"
        if profile_source.exists():
            try:
                shutil.copy2(profile_source, profile_target)
            except Exception:
                pass
    PROFILE_PATH = profile_target
    
    config_target = EXE_DIR / "config.json"
    if not config_target.exists():
        config_source = APP_ROOT / "config.json"
        if config_source.exists():
            try:
                shutil.copy2(config_source, config_target)
            except Exception:
                pass
    CONFIG_PATH = config_target
else:
    EXE_DIR = APP_ROOT
    PROFILE_PATH = APP_ROOT / "profiles.json"
    CONFIG_PATH = APP_ROOT / "config.json"

# Helper Config Loader functions
def load_env_file(exe_dir: Path):
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
            return
        except Exception as e:
            logger.error(f"Failed to load env file {env_path}: {e}")

def load_config(config_path: Path, exe_dir: Path) -> Dict:
    load_env_file(exe_dir)
    if not config_path.exists():
        return {}
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def save_config(config_path: Path, config: Dict):
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving config to {config_path}: {e}")

# Decorator to wrap API methods and return structured errors
def safe_api(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Unhandled Exception in API {func.__name__}: {e}", exc_info=True)
            return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
    return wrapper

# Thread-safe UI bridge
class ThreadSafeUIBridge:
    def __init__(self):
        self._window = None
        self._command_queue = queue.Queue()
        self._shutdown = False
        self._processor_thread = None
        self._lock = threading.Lock()
        
    def set_window(self, window):
        with self._lock:
            self._window = window
            if self._processor_thread is None or not self._processor_thread.is_alive():
                self._shutdown = False
                self._processor_thread = threading.Thread(
                    target=self._process_queue, 
                    name="UIBridgeProcessor",
                    daemon=True
                )
                self._processor_thread.start()
        
    def _process_queue(self):
        while not self._shutdown:
            try:
                js_code = self._command_queue.get(timeout=0.5)
                if self._window:
                    try:
                        self._window.evaluate_js(js_code)
                    except Exception as e:
                        pass
                self._command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                time.sleep(1)
    
    def evaluate_js_safe(self, js_code: str) -> None:
        self._command_queue.put(js_code)
        if self._window and (self._processor_thread is None or not self._processor_thread.is_alive()):
            self.set_window(self._window)
    
    def shutdown(self):
        self._shutdown = True
        self._processor_thread = None

_ui_bridge = ThreadSafeUIBridge()
def get_ui_bridge():
    return _ui_bridge

# Simplified Helper classes
class ProfileService:
    def __init__(self, file_path="profiles.json"):
        self.file_path = file_path
        self._lock = threading.Lock()
        
    def load_profiles(self):
        with self._lock:
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, "r") as f:
                        profiles = json.load(f)
                        return profiles
                except json.JSONDecodeError as e:
                    logger.error(f"Profile file corrupted: {e}")
                    backup_path = str(self.file_path) + ".backup"
                    if os.path.exists(backup_path):
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
                return {"profiles": {"Default": self.get_default_profile()}}

    def save_profiles(self, profiles):
        with self._lock:
            try:
                file_path_str = str(self.file_path)
                if os.path.exists(file_path_str):
                    backup_path = file_path_str + ".backup"
                    try:
                        shutil.copy2(file_path_str, backup_path)
                    except OSError:
                         logger.warning("Failed to create backup")
                
                temp_path = file_path_str + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(profiles, f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                
                max_retries = 5
                for i in range(max_retries):
                    try:
                        if os.path.exists(file_path_str):
                            os.replace(temp_path, file_path_str)
                        else:
                            os.rename(temp_path, file_path_str)
                        break
                    except OSError as e:
                        if e.winerror == 32 and i < max_retries - 1:
                            time.sleep(0.1)
                            continue
                        raise
                return {"status": "success", "message": "Profiles saved"}
            except Exception as e:
                logger.error(f"Error saving profiles: {e}")
                return {"status": "error", "message": str(e)}

    def export_profile(self, profile_name, data, file_path):
        export_data = {"name": profile_name, "data": data}
        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=4)

    def import_profile(self, file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data.get("name"), data.get("data")
        except Exception:
            return None, None

    def get_default_profile(self):
        return {"macros": {}, "keys": {}, "knobs": {}}

class AppIconService:
    def __init__(self):
        self._icon_cache = {}

    def get_app_icon(self, app_name: str, size: int = 32) -> Optional[str]:
        cache_key = f"{app_name}_{size}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        exe_path = self._find_executable_path(app_name)
        if not exe_path:
            return None
        
        icon_data = self._extract_icon_to_base64(exe_path, size)
        if icon_data:
            self._icon_cache[cache_key] = icon_data
            return icon_data
        return None

    def _find_via_registry(self, app_name: str) -> Optional[str]:
        for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for path in [
                rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{app_name}",
                rf"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\{app_name}"
            ]:
                try:
                    with winreg.OpenKey(root, path) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            val = val.strip('"')
                            if os.path.exists(val):
                                return val
                except WindowsError:
                    pass
        return None

    def _find_executable_path(self, app_name: str) -> Optional[str]:
        try:
            # 1. Registry query (instant & native App Paths)
            reg_path = self._find_via_registry(app_name)
            if reg_path:
                return reg_path

            # 2. Known paths check (instant)
            known_paths = self._get_known_app_paths(app_name.lower())
            for path in known_paths:
                if os.path.exists(path):
                    return path

            # 3. System32 check (instant)
            windows_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', app_name)
            if os.path.exists(windows_path):
                return windows_path

            # 4. Running processes (slower fallback)
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == app_name.lower():
                        if proc.info['exe'] and os.path.exists(proc.info['exe']):
                            return proc.info['exe']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 5. Program Files directory search (slowest fallback - removed slow APPDATA check)
            search_dirs = [
                os.environ.get('ProgramFiles', 'C:\\Program Files'),
                os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs'),
            ]
            for base_dir in search_dirs:
                if not os.path.exists(base_dir):
                    continue
                try:
                    for item in os.listdir(base_dir):
                        item_path = os.path.join(base_dir, item)
                        if os.path.isdir(item_path):
                            exe_path = os.path.join(item_path, app_name)
                            if os.path.exists(exe_path):
                                return exe_path
                except (PermissionError, OSError):
                    continue

            return None
        except Exception as e:
            logger.error(f"Error finding executable path for {app_name}: {e}")
            return None

    def _get_known_app_paths(self, app_name_lower: str) -> list:
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        
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
            'explorer.exe': ['C:\\Windows\\explorer.exe'],
            'notepad.exe': ['C:\\Windows\\System32\\notepad.exe'],
            'firefox.exe': [
                'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
                'C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe',
            ],
            'discord.exe': [os.path.join(localappdata, 'Discord', 'app-*', 'Discord.exe')],
            'slack.exe': [os.path.join(localappdata, 'slack', 'slack.exe')],
            'photoshop.exe': [
                'C:\\Program Files\\Adobe\\Adobe Photoshop 2024\\Photoshop.exe',
                'C:\\Program Files\\Adobe\\Adobe Photoshop 2023\\Photoshop.exe',
            ],
            'premiere.exe': [
                'C:\\Program Files\\Adobe\\Adobe Premiere Pro 2024\\Adobe Premiere Pro.exe',
                'C:\\Program Files\\Adobe\\Adobe Premiere Pro 2023\\Adobe Premiere Pro.exe',
            ],
            'obs64.exe': ['C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe'],
            'blender.exe': [
                'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe',
                'C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe',
            ],
        }
        
        paths = known_apps.get(app_name_lower, [])
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
        try:
            hicon = None
            try:
                large, small = win32gui.ExtractIconEx(exe_path, 0)
                if large or small:
                    if size > 16 and large:
                        hicon = large[0]
                        for icon in large[1:]: win32gui.DestroyIcon(icon)
                        for icon in small: win32gui.DestroyIcon(icon)
                    elif small:
                        hicon = small[0]
                        for icon in large: win32gui.DestroyIcon(icon)
                        for icon in small[1:]: win32gui.DestroyIcon(icon)
            except Exception as e:
                logger.debug(f"Standard extraction failed: {e}")
                
            if not hicon:
                try:
                    _shell32 = ctypes.windll.shell32
                    SHGFI_ICON = 0x000000100
                    SHGFI_LARGEICON = 0x000000000
                    SHGFI_SMALLICON = 0x000000001
                    
                    class SHFILEINFO(ctypes.Structure):
                        _fields_ = [
                            ("hIcon", ctypes.wintypes.HICON),
                            ("iIcon", ctypes.c_int),
                            ("dwAttributes", ctypes.wintypes.DWORD),
                            ("szDisplayName", ctypes.wintypes.WCHAR * 260),
                            ("szTypeName", ctypes.wintypes.WCHAR * 80)
                        ]
                    shfileinfo = SHFILEINFO()
                    flags = SHGFI_ICON
                    if size > 16:
                        flags |= SHGFI_LARGEICON
                    else:
                        flags |= SHGFI_SMALLICON
                    _shell32.SHGetFileInfoW(exe_path, 0, ctypes.byref(shfileinfo), ctypes.sizeof(shfileinfo), flags)
                    if shfileinfo.hIcon:
                        hicon = shfileinfo.hIcon
                except Exception as e:
                    logger.error(f"Shell fallback failed: {e}")

            if not hicon:
                return None
            
            hdc_handle = win32gui.GetDC(0)
            try:
                hdc = win32ui.CreateDCFromHandle(hdc_handle)
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, size, size)
                hdc_mem = hdc.CreateCompatibleDC()
                hdc_mem.SelectObject(hbmp)
                
                win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer('RGBA', (size, size), bmpstr, 'raw', 'BGRA', 0, 1)
                if img.getextrema()[3][1] == 0:
                     img = Image.frombuffer('RGB', (size, size), bmpstr, 'raw', 'BGRX', 0, 1).convert('RGBA')
                
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                hdc_mem.DeleteDC()
                hdc.DeleteDC()
                return f"data:image/png;base64,{img_base64}"
            finally:
                win32gui.ReleaseDC(0, hdc_handle)
                if hicon:
                    win32gui.DestroyIcon(hicon)
        except Exception as e:
            logger.error(f"Error extracting icon from {exe_path}: {e}")
            return None

    def clear_cache(self):
        self._icon_cache.clear()

class CommunityLibraryService:
    def __init__(self, config: Dict):
        self.config = config
        self.pb_url = config.get('pocketbase', {}).get('url', '')
        if not self.pb_url:
            self.pb_url = config.get('community', {}).get('submission_url', '')
        self.pb_url = self.pb_url.rstrip('/')
        
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=30)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._categories_cache = None
        self._macros_cache = {}
        self._window = None
        self._last_update = 0
        self._cache_ttl = 300
    
    def set_window(self, window):
        self._window = window
        
    def _load_local_manifest(self) -> List[Dict]:
        try:
            local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'macros'))
            local_path = os.path.join(local_dir, 'manifest.json')
            if os.path.exists(local_path):
                with open(local_path, 'r', encoding='utf-8') as lf:
                    manifest = json.load(lf)
                    for macro in manifest:
                        if '_metadata' not in macro:
                            macro['_metadata'] = {
                                'category': macro.get('category', 'other'),
                                'filename': f"{macro.get('name', 'unnamed')}.json",
                                'size': 0
                            }
                    return manifest
        except Exception as le:
            logger.warning(f"Could not load local manifest.json: {le}")
        return []

    def get_categories(self, force_refresh: bool = False) -> List[str]:
        macros = self.get_all_macros(force_refresh=force_refresh)
        categories = set(m.get('category', 'other') for m in macros)
        return sorted(list(categories))
    
    def get_macros_in_category(self, category: str, force_refresh: bool = False) -> List[Dict]:
        macros = self.get_all_macros(force_refresh=force_refresh)
        return [m for m in macros if m.get('category', '').lower() == category.lower()]
    
    def get_all_macros(self, sort_by: str = 'name', force_refresh: bool = False) -> List[Dict]:
        if not self.pb_url:
            return self._load_local_manifest()
            
        if 'all' in self._macros_cache and not force_refresh:
            all_macros = self._macros_cache['all']
        else:
            try:
                url = f"{self.pb_url}/api/collections/macros/records?filter=(approved=true)&perPage=500"
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    records = response.json().get('items', [])
                    all_macros = []
                    for record in records:
                        macro = {
                            "id": record.get("id"),
                            "name": record.get("name"),
                            "author": record.get("author"),
                            "description": record.get("description"),
                            "category": record.get("category", "other"),
                            "tags": record.get("tags", []),
                            "type": record.get("type", "macro"),
                            "likes": record.get("likes", 0),
                            "downloads": record.get("downloads", 0),
                            "uploaded_at": record.get("created"),
                        }
                        if record.get("type") == "profile":
                            macro["profile"] = record.get("profile_data", {})
                        else:
                            macro["macro"] = record.get("macro_data", {})
                            for k, v in record.get("macro_data", {}).items():
                                if k != "name":
                                    macro[k] = v
                        
                        macro['_metadata'] = {
                            'category': record.get('category', 'other'),
                            'filename': f"{record.get('name', 'unnamed')}.json",
                            'size': 0
                        }
                        all_macros.append(macro)
                    self._macros_cache['all'] = all_macros
                else:
                    logger.warning(f"PocketBase returned status {response.status_code}")
                    all_macros = self._load_local_manifest()
            except Exception as e:
                logger.error(f"Error fetching community macros from PocketBase: {e}")
                all_macros = self._load_local_manifest()
                
        sorted_macros = list(all_macros)
        if sort_by == 'name':
            sorted_macros.sort(key=lambda x: x.get('name', '').lower())
        elif sort_by == 'category':
            sorted_macros.sort(key=lambda x: x.get('category', '').lower())
        return sorted_macros
    
    def search_macros(self, query: str) -> List[Dict]:
        query_lower = query.lower()
        results = []
        macros = self.get_all_macros(sort_by='name')
        for macro in macros:
            if query_lower in macro.get('name', '').lower():
                results.append(macro)
                continue
            if query_lower in macro.get('description', '').lower():
                results.append(macro)
                continue
        return results

    def upload_macro(self, macro_data: Dict) -> Dict:
        try:
            if not self.pb_url:
                return {"status": "error", "message": "PocketBase not configured. Check config.json"}
                
            if not macro_data.get('name'):
                return {"status": "error", "message": "Invalid data: Missing name"}
                
            ctype = macro_data.get('type', 'macro')
            if ctype == 'profile':
                if not macro_data.get('profile'):
                    return {"status": "error", "message": "Invalid profile data"}
                profile_data = macro_data.get('profile', {})
                macro_content = {}
            else:
                base = macro_data.get('macro', macro_data)
                valid_keys = ['actions', 'command', 'path', 'commands', 'text']
                has_content = any(key in base for key in valid_keys)
                if not has_content:
                    return {"status": "error", "message": "Invalid macro data"}
                profile_data = {}
                macro_content = base

            payload = {
                "name": macro_data.get("name"),
                "author": macro_data.get("author", "Anonymous"),
                "description": macro_data.get("description", ""),
                "category": macro_data.get("category", "other"),
                "tags": macro_data.get("tags", []),
                "type": ctype,
                "macro_data": macro_content,
                "profile_data": profile_data,
                "approved": False
            }

            url = f"{self.pb_url}/api/collections/macros/records"
            response = self.session.post(url, json=payload, timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info("Successfully uploaded macro to PocketBase")
                self._update_local_manifest(macro_data)
                return {"status": "success", "message": "Macro submitted for review!"}
            else:
                error_msg = f"PocketBase submission failed (Status {response.status_code})"
                try:
                    error_json = response.json()
                    details = []
                    if 'message' in error_json:
                        details.append(error_json['message'])
                    if 'data' in error_json and isinstance(error_json['data'], dict):
                        field_errs = [f"{field}: {err.get('message', '')}" for field, err in error_json['data'].items() if isinstance(err, dict)]
                        if field_errs:
                            details.append("; ".join(field_errs))
                    if details:
                        error_msg += f": {' - '.join(details)}"
                except Exception:
                    pass
                return {"status": "error", "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

    def _update_local_manifest(self, macro_data: Dict):
        try:
            import datetime
            entry = {
                "name": macro_data.get("name"),
                "author": macro_data.get("author"),
                "description": macro_data.get("description"),
                "category": macro_data.get("category", "other"),
                "tags": macro_data.get("tags", []),
                "uploaded_at": datetime.datetime.now().isoformat()
            }
            ctype = macro_data.get("type", "macro")
            if ctype == "profile":
                entry["type"] = "profile"
                entry["profile"] = macro_data.get("profile", {})
            else:
                macro_content = macro_data.get("macro", {})
                for k, v in macro_content.items():
                    if k != "name":
                        entry[k] = v

            local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'macros'))
            local_path = os.path.join(local_dir, 'manifest.json')
            
            os.makedirs(local_dir, exist_ok=True)
            
            local_manifest = []
            if os.path.exists(local_path):
                try:
                    with open(local_path, 'r', encoding='utf-8') as lf:
                        local_manifest = json.load(lf)
                except Exception:
                    local_manifest = []
            
            local_manifest = [item for item in local_manifest if item.get("name") != entry.get("name")]
            local_manifest.insert(0, entry)
            
            with open(local_path, 'w', encoding='utf-8') as lf:
                json.dump(local_manifest, lf, indent=2)
            logger.info(f"Successfully updated local manifest.json at {local_path}")
        except Exception as le:
            logger.warning(f"Could not update local manifest.json: {le}")

    def increment_download(self, macro_id: str):
        if not self.pb_url or not macro_id:
            return
        try:
            url = f"{self.pb_url}/api/collections/macros/records/{macro_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                record = response.json()
                current_downloads = record.get("downloads", 0)
                patch_response = self.session.patch(url, json={"downloads": current_downloads + 1}, timeout=5)
                if patch_response.status_code == 200:
                    logger.info(f"Incremented downloads for macro {macro_id} to {current_downloads + 1}")
        except Exception as e:
            logger.warning(f"Failed to increment downloads on PocketBase: {e}")

    def increment_like(self, macro_id: str) -> Dict:
        if not self.pb_url or not macro_id:
            return {"status": "error", "message": "PocketBase not configured"}
        try:
            url = f"{self.pb_url}/api/collections/macros/records/{macro_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                record = response.json()
                current_likes = record.get("likes", 0)
                new_likes = current_likes + 1
                patch_response = self.session.patch(url, json={"likes": new_likes}, timeout=5)
                if patch_response.status_code == 200:
                    logger.info(f"Incremented likes (stars) for macro {macro_id} to {new_likes}")
                    if 'all' in self._macros_cache:
                        for m in self._macros_cache['all']:
                            if m.get('id') == macro_id:
                                m['likes'] = new_likes
                                break
                    return {"status": "success", "likes": new_likes}
            return {"status": "error", "message": "Failed to update record"}
        except Exception as e:
            logger.warning(f"Failed to increment likes on PocketBase: {e}")
            return {"status": "error", "message": str(e)}

    def decrement_like(self, macro_id: str) -> Dict:
        if not self.pb_url or not macro_id:
            return {"status": "error", "message": "PocketBase not configured"}
        try:
            url = f"{self.pb_url}/api/collections/macros/records/{macro_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                record = response.json()
                current_likes = record.get("likes", 0)
                new_likes = max(0, current_likes - 1)
                patch_response = self.session.patch(url, json={"likes": new_likes}, timeout=5)
                if patch_response.status_code == 200:
                    logger.info(f"Decremented likes (stars) for macro {macro_id} to {new_likes}")
                    if 'all' in self._macros_cache:
                        for m in self._macros_cache['all']:
                            if m.get('id') == macro_id:
                                m['likes'] = new_likes
                                break
                    return {"status": "success", "likes": new_likes}
            return {"status": "error", "message": "Failed to update record"}
        except Exception as e:
            logger.warning(f"Failed to decrement likes on PocketBase: {e}")
            return {"status": "error", "message": str(e)}

    def clear_cache(self):
        self._categories_cache = None
        self._macros_cache = {}

class FirmwareUpdateService:
    def __init__(self, config: Dict):
        self.config = config
        self.firmware_repo = config.get('github', {}).get('firmware_repo', '')
        self.app_repo = config.get('github', {}).get('app_repo', '')
        self.current_firmware_version = config.get('firmware', {}).get('current_version', '0.0.0')
        self.current_app_version = config.get('app', {}).get('current_version', '1.0.0')
 
    def _get_api_url(self, repo: str) -> Optional[str]:
        if not repo: return None
        return f"https://api.github.com/repos/{repo}/releases/latest"

    def _get_headers(self) -> Dict:
        return {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Overcontrol'}
    
    def _check_updates_generic(self, repo: str, current_version: str, asset_extension: str = '.bin') -> Dict:
        api_url = self._get_api_url(repo)
        if not api_url:
            return {'error': 'Repository not configured'}
        if current_version == "Unknown":
            return {'update_available': False, 'current_version': 'Unknown (Connect Device)', 'latest_version': 'Unknown'}
        try:
            req_headers = self._get_headers()
            response = requests.get(api_url, headers=req_headers, timeout=10)
            if response.status_code == 404:
                return {'error': 'Repository not found or no releases available'}
            if response.status_code == 403:
                return {'error': 'API Rate Limit Exceeded'}
            if response.status_code != 200:
                return {'error': f'API returned status {response.status_code}'}
            
            release_data = response.json()
            latest_version_str = release_data.get('tag_name', '0.0.0').lstrip('v')
            
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
            
            if not download_url and asset_extension in ('.bin', '.uf2'):
                 return {'error': f'No firmware binary ({asset_extension}) found'}

            try:
                is_newer = pkg_version.parse(latest_version_str) > pkg_version.parse(current_version)
            except Exception:
                is_newer = latest_version_str != current_version
            
            return {
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
        except Exception as e:
            return {'error': str(e)}

    def check_firmware_updates(self, current_version: str = None) -> Dict:
        ver = current_version if current_version is not None else self.current_firmware_version
        return self._check_updates_generic(self.firmware_repo, ver, '.uf2')

    def check_app_updates(self) -> Dict:
        return self._check_updates_generic(self.app_repo, self.current_app_version, '')
    
    def download_firmware(self, download_url: str, save_path: Path) -> bool:
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            req_headers = self._get_headers()
            response = requests.get(download_url, headers=req_headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            sha256_hash = hashlib.sha256()
            with open(save_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            calculated_hash = sha256_hash.hexdigest().lower()
            
            hash_found = False
            expected_hash = None
            req_headers = self._get_headers()
            
            for suffix in [".sha256", ".sha256.txt"]:
                sha_url = download_url + suffix
                try:
                    resp = requests.get(sha_url, headers=req_headers, timeout=10)
                    if resp.status_code == 200:
                        hash_text = resp.text.strip()
                        match = re.match(r'^([a-fA-F0-9]{64})', hash_text)
                        if match:
                            expected_hash = match.group(1).lower()
                            hash_found = True
                            break
                except Exception:
                    pass
                    
            if hash_found:
                if calculated_hash != expected_hash:
                    if save_path.exists():
                        save_path.unlink()
                    return False
            return True
        except Exception as e:
            logger.error(f"Error downloading firmware: {e}")
            return False
    
    def set_current_version(self, version: str):
        self.current_firmware_version = version

class UpdateManager:
    def __init__(self, config=None):
        self.config = config or {}
        if getattr(sys, 'frozen', False):
             self.app_root = Path(sys.executable).parent
        else:
             self.app_root = Path(__file__).parent.parent
        self.temp_dir = self.app_root / "temp_update"
        self._restart_timer = None
    
    def set_config(self, config):
        self.config = config

    def check_app_update(self):
        try:
            repo = self.config.get('github', {}).get('app_repo', '')
            if not repo:
                 return {'status': 'error', 'message': 'App repository not configured'}
            current_version = APP_VERSION
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Overcontrol'}
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                 return {'status': 'error', 'message': f'API error: {resp.status_code}'}
            data = resp.json()
            latest_version_str = data.get('tag_name', '0.0.0').lstrip('v')
            try:
                is_newer = pkg_version.parse(latest_version_str) > pkg_version.parse(current_version)
            except Exception:
                is_newer = latest_version_str != current_version
            
            download_url = None
            asset_name = None
            
            def find_asset(ext):
                for a in data.get('assets', []):
                    if a.get('name', '').endswith(ext):
                        return a
                return None

            asset = find_asset('.zip')
            if not asset:
                asset = find_asset('.exe')
            if asset:
                 download_url = asset.get('browser_download_url')
                 asset_name = asset.get('name')
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
            return {'status': 'error', 'message': str(e)}

    def download_update(self, url):
        try:
            if not url:
                return {'status': 'error', 'message': 'No download URL provided'}
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            filename = "update_package" + (".exe" if url.endswith(".exe") else ".zip")
            save_path = self.temp_dir / filename
            
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            sha256_hash = hashlib.sha256()
            with open(save_path, 'rb') as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            calculated_hash = sha256_hash.hexdigest().lower()
            
            headers = {'User-Agent': 'Overcontrol'}
            hash_found = False
            expected_hash = None
            
            for suffix in [".sha256", ".sha256.txt"]:
                sha_url = url + suffix
                try:
                    resp = requests.get(sha_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        hash_text = resp.text.strip()
                        match = re.match(r'^([a-fA-F0-9]{64})', hash_text)
                        if match:
                            expected_hash = match.group(1).lower()
                            hash_found = True
                            break
                except Exception:
                    pass
            if hash_found:
                if calculated_hash != expected_hash:
                    if save_path.exists():
                        os.remove(save_path)
                    return {'status': 'error', 'message': 'Update package integrity check failed.'}
            
            if filename.endswith(".zip"):
                 import zipfile
                 with zipfile.ZipFile(save_path, 'r') as zip_ref:
                      zip_ref.extractall(self.temp_dir)
                 os.remove(save_path)
                 contents = [c for c in self.temp_dir.iterdir() if not c.name.startswith('.')]
                 if len(contents) == 1 and contents[0].is_dir():
                      for item in contents[0].iterdir():
                          shutil.move(str(item), str(self.temp_dir))
                      contents[0].rmdir()
                 if not getattr(sys, 'frozen', False):
                      self._cleanup_dev_update()
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _cleanup_dev_update(self):
        for root, dirs, files in os.walk(self.temp_dir):
             if 'app' in dirs:
                  app_dir = Path(root) / 'app'
                  assets_dir = app_dir / 'assets'
                  if assets_dir.exists():
                       try:
                           shutil.rmtree(assets_dir)
                       except Exception:
                           pass
                  break

    def trigger_restart(self):
        self._restart_timer = threading.Timer(0.5, self._restart_sequence)
        self._restart_timer.start()
        return {'status': 'success', 'message': 'Restarting...'}

    def _restart_sequence(self):
        try:
            batch_script = self.app_root / "update_installer.bat"
            is_frozen = getattr(sys, 'frozen', False)
            current_pid = os.getpid()
            if is_frozen:
                executable = f'"{sys.executable}"'
            else:
                executable = f'"{sys.executable}" "{self.app_root / "run.py"}"'
            kill_cmd = f'taskkill /PID {current_pid} /F'
            
            script_content = f"""@echo off
title Updating Overcontrol...
color 0b
echo Waiting for application to close (PID: {current_pid})...
timeout /t 2 /nobreak >nul
{kill_cmd} >nul 2>&1
echo Install started...
set "SOURCE={self.temp_dir}"
set "DEST={self.app_root}"
xcopy "%SOURCE%\\*" "%DEST%\\" /E /H /Y /C /I
echo Update applied.
echo Cleaning up...
rmdir /s /q "%SOURCE%"
echo Restarting application...
start "" {executable}
exit
"""
            with open(batch_script, "w") as f:
                f.write(script_content)
            subprocess.Popen([str(batch_script)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            os._exit(0)
        except Exception as e:
            logger.error(f"Restart sequence failed: {e}")

# Consolidated Api class
class Api:
    def __init__(self):
        self._app_root = APP_ROOT
        self._webview = webview
        self._config = self._load_config()
        
        # Initialize simplified services
        self._profile_service = ProfileService(PROFILE_PATH)
        self._macro_execution_service = MacroExecutionService()
        self._macro_execution_service.macro_resolver = self._resolve_macro_for_execution
        self._macro_recording_service = MacroRecordingService()
        self._window_control_service = WindowControlService()
        self._serial_service = SerialService()
        self._knob_controller = KnobController(self._execute_knob_callback)
        self._ui_bridge = get_ui_bridge()
        
        self._firmware_update_service = FirmwareUpdateService(self._config)
        self._community_library_service = CommunityLibraryService(self._config)
        self._update_manager = UpdateManager(self._config)
        self._app_icon_service = AppIconService()
        
        self._profile_switcher = ProfileSwitcherService(
            self._config, 
            on_profile_switch=self._auto_switch_profile
        )
        
        # State
        self._profiles = self._profile_service.load_profiles()
        self._current_profile_name = self._profiles.get("active_profile", "Default Profile")
        
        if self._current_profile_name:
            self._profile_switcher.notify_manual_switch(self._current_profile_name)
            
        self.tray_enabled = self._profiles.get("minimize_to_tray", False)
        self.current_theme = "dark"
        self.current_accent_color = self._profiles.get("accent_color", "#0091ff")
        self.firmware_version = self._config.get('firmware', {}).get('current_version', 'Unknown')
        self.tray_icon = None
        self.tray_loop_running = True
        self._tray_update_callback = None
        
        self._serial_service.on_message_callback = self.on_serial_message
        self._serial_service.on_connection_lost_callback = self.on_serial_connection_lost
        
        self._window = None
        self._icon_cache = None
        
        self._profile_switcher.start()
        logger.info("API initialized successfully (Consolidated)")

    def set_window(self, window):
        self._window = window
        self._community_library_service.set_window(window)
        self._ui_bridge.set_window(window)
        self._macro_recording_service.set_ui_bridge(self._ui_bridge)
        logger.info("Window reference set")

    def set_tray_update_callback(self, callback):
        self._tray_update_callback = callback

    def update_tray(self):
        if self._tray_update_callback:
            self._tray_update_callback()

    def _load_config(self) -> Dict:
        return load_config(CONFIG_PATH, EXE_DIR)
    
    def _save_config(self):
        save_config(CONFIG_PATH, self._config)

    def _send_toast_notification(self, title, message):
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Overcontrol")
        $notifier.Show($notification)
        """
        try:
            subprocess.run(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            logger.error(f"Failed to send toast: {e}")

    def _auto_switch_profile(self, profile_name: str):
        try:
            if profile_name in self._profiles.get("profiles", {}):
                result = self.set_active_profile(profile_name, is_auto=True)
                if result.get('status') == 'success':
                    if self._window:
                        safe_name = json.dumps(profile_name)
                        self._ui_bridge.evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")
                    self._send_toast_notification(f"Profile Switched to {profile_name}", "")
                    logger.info(f"Auto-switched to profile: {profile_name}")
                else:
                    logger.error(f"Failed to auto-switch to profile: {profile_name}")
        except Exception as e:
            logger.error(f"Error in auto-switch callback: {e}")

    @safe_api
    def on_serial_message(self, message: str):
        if message.startswith("VERSION_"):
            version = message.replace("VERSION_", "").strip()
            self.firmware_version = version
            if 'firmware' not in self._config:
                self._config['firmware'] = {}
            self._config['firmware']['current_version'] = version
            self._save_config()
            logger.info(f"Firmware version detected and saved: {version}")
            if self._window:
                safe_version = json.dumps(version)
                self._ui_bridge.evaluate_js_safe(f"window.onFirmwareVersion({safe_version})")
            self.update_tray()
            return {"status": "success"}
        
        self._handle_serial_command(message)
        if self._window:
            safe_msg = json.dumps(message)
            self._ui_bridge.evaluate_js_safe(f"window.onSerialMessage({safe_msg})")
        return {"status": "success"}

    def on_serial_connection_lost(self):
        logger.warning("Serial connection lost")
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")
        self.update_tray()

    @safe_api
    def get_knob_reverse(self):
        enabled = self._config.get("knob", {}).get("reverse_direction", False)
        return {"status": "success", "enabled": enabled}

    @safe_api
    def set_knob_reverse(self, enabled):
        if "knob" not in self._config:
            self._config["knob"] = {}
        self._config["knob"]["reverse_direction"] = enabled
        self._save_config()
        return {"status": "success"}

    @safe_api
    def browse_file_or_app(self):
        result = self._window.create_file_dialog(webview.OPEN_DIALOG)
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}
    
    @safe_api
    def get_app_icon(self, app_name: str):
        icon_data = self._app_icon_service.get_app_icon(app_name)
        if icon_data:
            return {"status": "success", "icon": icon_data}
        else:
            return {"status": "error", "message": "Icon not found"}

    # --- ProfileMixin Endpoints ---
    @safe_api
    def get_profiles(self):
        self._profiles = self._profile_service.load_profiles()
        rules = self._config.get("auto_switching", {}).get("rules", {})
        profiles_data = self._profiles.get("profiles", {})
        for profile_name in profiles_data:
            linked_apps = [app for app, prof in rules.items() if prof == profile_name]
            profiles_data[profile_name]["linked_apps"] = linked_apps
        return self._profiles

    @safe_api
    def save_profiles(self, profiles):
        if not isinstance(profiles, dict):
            return {"status": "error", "message": "Invalid profiles format"}
        if "profiles" in profiles:
            self._profiles["profiles"] = profiles["profiles"]
        if "active_profile" in profiles:
             self._profiles["active_profile"] = profiles["active_profile"]
        if "active_profile" not in self._profiles:
             self._profiles["active_profile"] = self._current_profile_name
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    @safe_api
    def set_active_profile(self, profile_name: str, is_auto: bool = False):
        if not isinstance(profile_name, str) or not profile_name:
            return {"status": "error", "message": "Invalid profile name"}
        if profile_name not in self._profiles.get("profiles", {}):
            return {"status": "error", "message": "Profile not found"}
        self._current_profile_name = profile_name
        if not is_auto and self._profile_switcher:
             self._profile_switcher.notify_manual_switch(profile_name)
        self._profiles["active_profile"] = profile_name
        self._profile_service.save_profiles(self._profiles)
        
        profile_data = self._profiles.get("profiles", {}).get(profile_name, {})
        knob_mode = profile_data.get("knob_mode", "Standard")
        knob_speed = profile_data.get("knob_speed", 1)
        self._knob_controller.set_mode(knob_mode)
        self._knob_controller.set_speed(knob_speed)
        
        if self._serial_service.is_connected:
            self._serial_service.send_raw_command(f"SET_KNOB_MODE {knob_mode}")
        return {"status": "success"}

    @safe_api
    def set_knob_mode(self, mode):
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_mode"] = mode
            self._profile_service.save_profiles(self._profiles)
        self._knob_controller.set_mode(mode)
        if self._serial_service.is_connected:
            self._serial_service.send_raw_command(f"SET_KNOB_MODE {mode}")
        return {"status": "success"}

    @safe_api
    def set_knob_speed(self, speed):
        if self._current_profile_name in self._profiles.get("profiles", {}):
            self._profiles["profiles"][self._current_profile_name]["knob_speed"] = speed
            self._profile_service.save_profiles(self._profiles)
        self._knob_controller.set_speed(speed)
        return {"status": "success"}

    @safe_api
    def reset_to_defaults(self):
        default = self._profile_service.get_default_profile()
        self._profiles = {
            "profiles": {"Default Profile": default},
            "active_profile": "Default Profile",
            "minimize_to_tray": False 
        }
        self.tray_enabled = False
        self._current_profile_name = "Default Profile"
        self._profile_service.save_profiles(self._profiles)
        self._knob_controller.set_mode("Standard")
        self._knob_controller.set_speed(1)
        if self._serial_service.is_connected:
            self._serial_service.send_raw_command("SET_KNOB_MODE Standard")
        return {"status": "success"}

    # --- SerialMixin Endpoints ---
    @safe_api
    def get_serial_ports(self):
        return self._serial_service.get_available_ports()

    @safe_api
    def connect_serial(self, port):
        success = self._serial_service.connect(port)
        if success:
            if self._window:
                safe_port = json.dumps(port)
                self._ui_bridge.evaluate_js_safe(f"window.onSerialConnected({safe_port})")
            self.update_tray()
            profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
            knob_mode = profile_data.get("knob_mode", "Standard")
            def sync_knob_mode():
                time.sleep(1.5)
                if self._serial_service.is_connected:
                    self._serial_service.send_raw_command(f"SET_KNOB_MODE {knob_mode}")
            threading.Thread(target=sync_knob_mode, daemon=True).start()
        return {"status": "success", "connected": success} if success else {"status": "error", "message": "Connection failed"}

    @safe_api
    def disconnect_serial(self):
        self._serial_service.disconnect()
        self._serial_service._last_connected_port = None
        if self._window:
            self._ui_bridge.evaluate_js_safe("window.onSerialConnectionLost()")
        self.update_tray()
        return {"status": "success"}
    
    @safe_api
    def is_connected(self):
        return self._serial_service.is_connected

    # --- SystemMixin Endpoints ---
    @safe_api
    def window_minimize(self):
        if self._macro_recording_service:
            try:
                self._macro_recording_service.stop_recording(is_emergency=True)
            except Exception as e:
                logger.error(f"Error stopping macro recording on minimize: {e}")
        if self._window:
            self._window.minimize()
            
    @safe_api
    def window_close(self):
        if self._macro_recording_service:
            try:
                self._macro_recording_service.stop_recording(is_emergency=True)
            except Exception as e:
                logger.error(f"Error stopping macro recording on close: {e}")
        if self._window:
            if self.tray_enabled:
                 self._window.hide()
            else:
                 self._window.destroy()

    @safe_api
    def get_startup_status(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "MacropadPro")
            winreg.CloseKey(key)
            return {"status": "success", "enabled": True}
        except WindowsError:
            return {"status": "success", "enabled": False}

    @safe_api
    def set_startup_status(self, enabled):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}" --minimized'
                else:
                    main_script = APP_ROOT / "app" / "main.py"
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

    @safe_api
    def get_auto_switch_status(self):
        enabled = self._config.get("auto_switching", {}).get("enabled", True)
        return {"status": "success", "enabled": enabled}

    @safe_api
    def set_auto_switch_enabled(self, enabled):
        if "auto_switching" not in self._config:
            self._config["auto_switching"] = {}
        self._config["auto_switching"]["enabled"] = enabled
        self._save_config()
        self._profile_switcher.update_config(self._config)
        return {"status": "success"}

    @safe_api
    def get_tray_status(self):
        return {"status": "success", "enabled": self.tray_enabled}

    @safe_api
    def set_tray_status(self, enabled):
        self.tray_enabled = enabled
        self._profiles["minimize_to_tray"] = enabled
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    @safe_api
    def get_theme(self):
        return {"status": "success", "theme": self.current_theme}
    
    @safe_api
    def set_theme(self, theme):
        self.current_theme = "dark" 
        self._profiles["theme"] = "dark"
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    @safe_api
    def get_accent_color(self):
        return {"status": "success", "accent_color": self.current_accent_color}

    @safe_api
    def set_accent_color(self, color):
        self.current_accent_color = color
        self._profiles["accent_color"] = color
        self._profile_service.save_profiles(self._profiles)
        return {"status": "success"}

    @safe_api
    def get_saved_colors(self):
        saved = self._profiles.get("saved_colors", [])
        return {"status": "success", "colors": saved}

    @safe_api
    def add_saved_color(self, color):
        saved = self._profiles.get("saved_colors", [])
        if color not in saved:
            saved.append(color)
            self._profiles["saved_colors"] = saved
            self._profile_service.save_profiles(self._profiles)
        return {"status": "success", "colors": saved}

    @safe_api
    def remove_saved_color(self, color):
        saved = self._profiles.get("saved_colors", [])
        if color in saved:
            saved.remove(color)
            self._profiles["saved_colors"] = saved
            self._profile_service.save_profiles(self._profiles)
        return {"status": "success", "colors": saved}

    # --- CommunityMixin Endpoints ---
    @safe_api
    def get_community_categories(self):
        categories = self._community_library_service.get_categories()
        return {"status": "success", "categories": categories}
    
    @safe_api
    def get_community_macros(self, category: str = None, search: str = None, force_refresh: bool = False):
        if search:
            macros = self._community_library_service.search_macros(search)
        elif category:
            macros = self._community_library_service.get_macros_in_category(category, force_refresh=force_refresh)
        else:
            macros = self._community_library_service.get_all_macros(force_refresh=force_refresh)
        return {"status": "success", "macros": macros}
    
    @safe_api
    def install_community_macro(self, macro_data: Dict, increment_download: bool = True):
        install_type = macro_data.get('type', 'macro')
        macro_id = macro_data.get('id')
        
        if install_type == 'profile':
            profile_content = macro_data.get('profile', {})
            if not profile_content:
                return {"status": "error", "message": "Invalid profile data"}
            profile_content['origin'] = 'community-profile'
            base_name = macro_data.get('name', 'Community Profile')
            profile_name = base_name
            counter = 1
            while profile_name in self._profiles.get("profiles", {}):
                profile_name = f"{base_name} ({counter})"
                counter += 1
            self._profiles["profiles"][profile_name] = profile_content
            self._profiles["active_profile"] = profile_name 
            self._current_profile_name = profile_name
            self._profile_service.save_profiles(self._profiles)
            self._profile_switcher.notify_manual_switch(profile_name)
            if macro_id and increment_download:
                threading.Thread(target=self._community_library_service.increment_download, args=(macro_id,), daemon=True).start()
            return {"status": "success", "name": profile_name, "type": "profile"}
        else:
            macro_content = macro_data.get('macro', macro_data)
            macro_content['origin'] = 'community'
            profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
            if 'macros' not in profile_data:
                profile_data['macros'] = {}
            macro_name = macro_data.get('name', 'Unnamed Macro')
            base_name = macro_name
            counter = 1
            while macro_name in profile_data['macros']:
                macro_name = f"{base_name} ({counter})"
                counter += 1
            profile_data['macros'][macro_name] = macro_content
            self._profiles["profiles"][self._current_profile_name] = profile_data
            self._profile_service.save_profiles(self._profiles)
            if macro_id and increment_download:
                threading.Thread(target=self._community_library_service.increment_download, args=(macro_id,), daemon=True).start()
            return {"status": "success", "name": macro_name, "type": "macro"}

    @safe_api
    def submit_community_macro(self, macro_data: Dict):
        return self._community_library_service.upload_macro(macro_data)

    @safe_api
    def like_community_macro(self, macro_id: str):
        return self._community_library_service.increment_like(macro_id)

    @safe_api
    def unlike_community_macro(self, macro_id: str):
        return self._community_library_service.decrement_like(macro_id)

    @safe_api
    def get_starred_macros(self):
        starred = self._config.get('starred_macros', [])
        return {"status": "success", "starred": starred}

    @safe_api
    def toggle_star_macro_state(self, macro_id: str, starred: bool):
        if not macro_id:
            return {"status": "error", "message": "Missing macro ID"}
        if 'starred_macros' not in self._config:
            self._config['starred_macros'] = []
        current_starred = set(self._config.get('starred_macros', []))
        if starred:
            current_starred.add(macro_id)
        else:
            current_starred.discard(macro_id)
        self._config['starred_macros'] = sorted(list(current_starred))
        self._save_config()
        return {"status": "success", "starred": self._config['starred_macros']}

    # --- IconMixin Endpoints ---
    @safe_api
    def get_icon_categories(self):
        icons_dir = self._app_root / "app" / "assets" / "icons"
        if not icons_dir.exists():
            return {"status": "success", "data": []}
        categories = [d.name for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        return {"status": "success", "data": sorted(categories)}

    @safe_api
    def get_icons(self, category):
        icons_dir = self._app_root / "app" / "assets" / "icons" / category
        if not icons_dir.exists():
            return {"status": "error", "message": "Category not found"}
        valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
        icons = []
        for f in icons_dir.iterdir():
            if f.is_file() and f.suffix.lower() in valid_exts:
                icons.append(f"icons/{category}/{f.name}")
        return {"status": "success", "data": sorted(icons)}

    def _ensure_icon_cache(self):
        if self._icon_cache is not None:
            return
        try:
            icons_dir = self._app_root / "app" / "assets" / "icons"
            if not icons_dir.exists():
                self._icon_cache = {}
                return
            data = {}
            valid_exts = {'.png', '.svg', '.jpg', '.jpeg', '.gif'}
            categories = sorted([d for d in icons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')])
            for category_dir in categories:
                cat_name = category_dir.name
                icons = []
                for f in category_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        icons.append(f"icons/{cat_name}/{f.name}")
                if icons:
                    data[cat_name] = sorted(icons)
            self._icon_cache = data
        except Exception as e:
            logger.error(f"Error building icon cache: {e}")
            self._icon_cache = {}

    @safe_api
    def get_all_icons_grouped(self):
        self._ensure_icon_cache()
        return {"status": "success", "data": self._icon_cache}

    @safe_api
    def search_icons(self, query):
        self._ensure_icon_cache()
        query = query.lower()
        
        synonym_map = {
            "settings": ["options", "gear", "cog", "preferences", "setup", "config", "control", "tool"],
            "options": ["settings", "preferences", "config", "menu"],
            "gear": ["settings", "cog", "preferences", "setup", "config"],
            "cog": ["settings", "gear", "preferences", "setup", "config"],
            "delete": ["remove", "trash", "bin", "clear", "erase", "trashcan", "discard"],
            "trash": ["delete", "remove", "bin", "clear", "erase", "trashcan", "discard"],
            "bin": ["delete", "remove", "trash", "clear", "erase", "trashcan", "discard"],
            "clear": ["delete", "remove", "trash", "erase", "clean", "reset"],
            "edit": ["write", "pen", "pencil", "modify", "change", "compose", "draft"],
            "pen": ["edit", "write", "pencil", "modify", "change"],
            "pencil": ["edit", "write", "pen", "modify", "change"],
            "add": ["plus", "create", "new", "insert", "more", "append"],
            "plus": ["add", "create", "new", "insert", "more"],
            "new": ["add", "create", "plus", "insert"],
            "create": ["add", "new", "plus", "insert"],
            "close": ["exit", "cancel", "remove", "xmark", "cross", "quit", "stop", "close-circle"],
            "exit": ["close", "quit", "leave", "logout"],
            "cancel": ["close", "exit", "remove", "xmark", "cross", "stop"],
            "cross": ["close", "cancel", "xmark", "remove"],
            "check": ["confirm", "ok", "success", "done", "tick", "approve", "yes", "valid", "checkbox"],
            "confirm": ["check", "ok", "success", "done", "tick", "approve"],
            "ok": ["check", "confirm", "success", "done", "tick", "approve", "yes"],
            "success": ["check", "confirm", "ok", "done", "tick", "green"],
            "done": ["check", "confirm", "ok", "success", "tick"],
            "tick": ["check", "confirm", "ok", "success", "done"],
            "search": ["find", "lookup", "magnify", "glass", "detect", "zoom", "query"],
            "find": ["search", "lookup", "magnifying", "glass"],
            "zoom": ["search", "find", "magnify", "scale", "size"],
            "home": ["house", "start", "main", "homepage", "dashboard"],
            "house": ["home", "start", "main"],
            "user": ["profile", "member", "avatar", "person", "human", "account", "contact", "people"],
            "profile": ["user", "member", "avatar", "person", "human", "account", "contact"],
            "avatar": ["user", "profile", "member", "person", "human", "account"],
            "member": ["user", "profile", "avatar", "person", "people"],
            "person": ["user", "profile", "avatar", "member", "human"],
            "people": ["users", "group", "team", "contacts", "crowd"],
            "mail": ["email", "envelope", "letter", "message", "inbox", "send"],
            "email": ["mail", "envelope", "letter", "message", "inbox", "send"],
            "envelope": ["mail", "email", "letter", "message"],
            "phone": ["call", "mobile", "telephone", "cellphone", "ring"],
            "call": ["phone", "mobile", "telephone", "ring"],
            "mobile": ["phone", "call", "telephone", "cellphone", "device"],
            "camera": ["photo", "capture", "lens", "snap", "shot", "picture"],
            "photo": ["camera", "capture", "lens", "snap", "picture", "image", "gallery"],
            "picture": ["photo", "image", "gallery", "art", "paint"],
            "image": ["photo", "picture", "gallery", "art", "paint"],
            "video": ["movie", "film", "play", "record", "camcorder", "media", "youtube"],
            "movie": ["video", "film", "play", "media"],
            "film": ["video", "movie", "play", "media", "camera"],
            "music": ["audio", "song", "sound", "melody", "tune", "track", "spotify", "playlist"],
            "song": ["music", "audio", "sound", "melody", "tune", "track"],
            "sound": ["music", "audio", "volume", "speaker", "noise"],
            "audio": ["music", "sound", "volume", "speaker", "track"],
            "volume": ["sound", "audio", "speaker", "loud", "level"],
            "speaker": ["volume", "sound", "audio", "loud"],
            "play": ["start", "run", "media", "music", "video", "go"],
            "pause": ["hold", "wait", "media", "music", "video", "stop"],
            "stop": ["halt", "end", "media", "music", "video", "block"],
            "lock": ["secure", "private", "safe", "key", "password", "security", "padlock"],
            "unlock": ["open", "public", "key", "password", "security", "unlocked"],
            "secure": ["lock", "private", "safe", "security"],
            "safe": ["lock", "secure", "private", "security", "shield"],
            "shield": ["safe", "secure", "security", "protect", "guard"],
            "key": ["lock", "unlock", "password", "security", "license"],
            "password": ["lock", "unlock", "key", "security", "passcode"],
            "cloud": ["weather", "sky", "storage", "backup", "download", "upload", "online"],
            "backup": ["cloud", "storage", "save", "sync"],
            "storage": ["cloud", "backup", "disk", "folder", "drive", "harddrive"],
            "sun": ["weather", "day", "light", "sunny", "brightness", "warm", "summer"],
            "sunny": ["sun", "weather", "day", "light"],
            "light": ["sun", "sunny", "brightness", "day", "lamp", "bulb"],
            "brightness": ["sun", "light", "screen"],
            "moon": ["weather", "night", "dark", "sleep", "midnight", "crescent"],
            "night": ["moon", "weather", "dark", "sleep"],
            "dark": ["moon", "night", "sleep"],
            "star": ["favorite", "bookmark", "rate", "like", "starry", "badge", "award"],
            "favorite": ["star", "heart", "bookmark", "like", "love"],
            "bookmark": ["star", "favorite", "tag", "label", "save"],
            "heart": ["love", "like", "favorite", "health", "medical", "cardio"],
            "love": ["heart", "like", "favorite"],
            "like": ["heart", "love", "star", "favorite", "thumbsup", "thumbs-up"],
            "map": ["location", "gps", "direction", "navigation", "address", "route", "compass"],
            "location": ["map", "gps", "direction", "navigation", "pin", "marker"],
            "gps": ["map", "location", "direction", "navigation"],
            "navigation": ["map", "location", "gps", "direction", "compass", "steer", "route"],
            "pin": ["marker", "location", "gps", "map", "anchor", "pushpin"],
            "marker": ["pin", "location", "gps", "map"],
            "info": ["about", "details", "help", "information", "hint"],
            "about": ["info", "details", "information"],
            "details": ["info", "about", "information"],
            "help": ["question", "faq", "support", "info", "guide", "assist"],
            "question": ["help", "faq", "support", "query", "ask"],
            "faq": ["help", "question", "support"],
            "support": ["help", "question", "faq", "assist"],
            "alert": ["warning", "error", "danger", "caution", "exclamation", "notice", "bell"],
            "warning": ["alert", "error", "danger", "caution", "exclamation", "notice"],
            "error": ["alert", "warning", "danger", "caution", "fail", "failure", "wrong"],
            "danger": ["alert", "warning", "error", "caution", "fail", "hazard"],
            "caution": ["alert", "warning", "error", "danger", "notice", "hazard"],
            "folder": ["directory", "storage", "file", "archive", "cabinet"],
            "directory": ["folder", "storage", "file"],
            "file": ["document", "paper", "page", "sheet", "text", "file-text"],
            "document": ["file", "paper", "page", "sheet", "text"],
            "paper": ["file", "document", "page", "sheet"],
            "page": ["file", "document", "paper", "sheet"],
            "sheet": ["file", "document", "paper", "page"],
            "copy": ["duplicate", "clone", "copy-file", "files"],
            "duplicate": ["copy", "clone"],
            "clone": ["copy", "duplicate"],
            "paste": ["clipboard", "insert", "output"],
            "clipboard": ["paste", "insert", "board", "copy-paste"],
            "cut": ["scissors", "crop", "divide"],
            "scissors": ["cut", "crop"],
            "undo": ["back", "reverse", "history", "previous", "arrow-left"],
            "redo": ["forward", "advance", "next", "arrow-right"],
            "save": ["disk", "floppy", "store", "download", "write"],
            "disk": ["save", "floppy", "storage", "drive"],
            "floppy": ["save", "disk", "storage"],
            "replace": ["swap", "exchange", "refresh", "rotate"],
            "swap": ["replace", "exchange", "switch"],
            "tab": ["window", "sheet", "browser", "page"],
            "window": ["tab", "browser", "screen", "display"],
            "refresh": ["reload", "sync", "update", "restart", "refresh-arrow"],
            "reload": ["refresh", "sync", "update"],
            "sync": ["refresh", "reload", "update", "connect", "arrows"],
            "update": ["refresh", "reload", "sync", "download"],
            "minimize": ["subtract", "hide", "down", "minus", "collapse"],
            "restore": ["maximize", "expand", "up", "reset"],
            "maximize": ["restore", "expand", "up", "fullscreen"],
            "expand": ["maximize", "restore", "fullscreen", "grow"],
            "mute": ["silent", "quiet", "volume-mute", "speaker-mute"],
            "silent": ["mute", "quiet"],
            "next": ["forward", "skip", "arrow-right", "ahead"],
            "previous": ["back", "prev", "arrow-left", "behind"],
            "prev": ["previous", "back", "arrow-left"],
            "skip": ["next", "forward"],
            "link": ["chain", "connect", "hyperlink", "url", "anchor"],
            "connect": ["link", "chain", "plug", "sync"],
            "disconnect": ["unlink", "unplug", "broken"],
            "lock-line": ["lock", "secure"],
            "lock-fill": ["lock", "secure"],
            "bell": ["alert", "alarm", "notify", "notification", "ring"],
            "notification": ["bell", "alert", "alarm", "notify"],
            "notify": ["bell", "alert", "alarm", "notification"],
            "mail-send": ["mail", "email", "send", "paperplane", "paper-plane"],
            "send": ["mail", "email", "paperplane", "paper-plane", "airplane", "fly"],
            "paperplane": ["send", "mail", "fly"],
            "airplane": ["send", "fly", "flight", "plane", "travel"],
            "terminal": ["console", "command", "bash", "cmd", "prompt", "code", "cli"],
            "console": ["terminal", "command", "bash", "cmd", "prompt", "code", "cli"],
            "code": ["terminal", "console", "develop", "coding", "source", "programming"],
            "develop": ["code", "coding", "source", "programming", "brackets", "build"],
            "brackets": ["code", "develop", "coding", "brackets"],
            "heart-fill": ["heart", "love", "like"],
            "heart-line": ["heart", "love", "like"],
            "star-fill": ["star", "favorite"],
            "star-line": ["star", "favorite"],
            "volume-up": ["volume", "loud", "sound"],
            "volume-down": ["volume", "quiet", "sound"],
            "volume-mute": ["mute", "silent", "quiet"]
        }
        
        matches = []
        for category, icons in self._icon_cache.items():
            category_lower = category.lower()
            for icon_path in icons:
                filename = icon_path.split('/')[-1].lower()
                base_name = re.sub(r'\.(svg|png|jpg|jpeg|gif)$', '', filename)
                
                # Split base name on delimiters
                words = re.split(r'[-_]', base_name)
                
                # Gather match keywords
                match_keys = {filename, base_name, category_lower}
                for word in words:
                    if word:
                        match_keys.add(word)
                        if word in synonym_map:
                            match_keys.update(synonym_map[word])
                            
                # Check if query matches any tag as substring
                if any(query in key for key in match_keys):
                    matches.append(icon_path)
                    
        return {"status": "success", "data": sorted(matches)}

    # --- UpdateMixin Endpoints ---
    @safe_api
    def check_for_updates(self):
        firmware_result = self._firmware_update_service.check_firmware_updates(self.firmware_version)
        app_result = self._update_manager.check_app_update()
        return {"status": "success", "firmware": firmware_result, "app": app_result}

    @safe_api
    def check_firmware_updates(self):
        return self._firmware_update_service.check_firmware_updates(self.firmware_version)

    @safe_api
    def check_app_updates(self):
        return self._update_manager.check_app_update()

    @safe_api
    def download_app_update(self, download_url):
        return self._update_manager.download_update(download_url)

    @safe_api
    def trigger_app_restart(self):
        return self._update_manager.trigger_restart()
    
    @safe_api
    def download_firmware_update(self, download_url: str):
        save_path = self._app_root / "firmware" / "update.uf2"
        success = self._firmware_update_service.download_firmware(download_url, save_path)
        if success:
            return {"status": "success", "path": str(save_path)}
        else:
            return {"status": "error", "message": "Download failed"}
            
    @safe_api
    def get_firmware_version(self):
        return {"status": "success", "version": self.firmware_version}

    @safe_api
    def get_app_version(self):
        return {"status": "success", "version": APP_VERSION}

    @safe_api
    def select_firmware_file(self):
        result = self._window.create_file_dialog(self._webview.OPEN_DIALOG, file_types=("UF2 Files (*.uf2)", "Bin Files (*.bin)", "All Files (*.*)"))
        if result and len(result) > 0:
            return {"status": "success", "path": result[0]}
        return {"status": "cancelled"}

    @safe_api
    def flash_firmware(self, port, file_path):
        if getattr(self, '_flasher', None) and self._flasher.is_flashing:
            return {"status": "error", "message": "A flashing operation is already in progress."}

        if not port and self._serial_service.is_connected:
            port = self._serial_service.port
        if not port:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            if ports:
                port = ports[0].device
            else:
                 return {"status": "error", "message": "No device found. Connect via USB."}

        def on_progress(msg, pct):
            if self._window:
                try:
                    safe_msg = json.dumps(msg)
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashProgress({safe_msg}, {pct})")
                except Exception as e:
                    logger.error(f"Error sending progress: {e}")

        def on_finished(success, msg):
            if self._window:
                try:
                    safe_msg = json.dumps(msg)
                    js_bool = "true" if success else "false"
                    self._ui_bridge.evaluate_js_safe(f"window.onFlashFinished({js_bool}, {safe_msg})")
                except Exception as e:
                    logger.error(f"Error sending completion: {e}")
            
        self._flasher = FlasherService(on_progress, on_finished)
        
        def run_flash_async():
            try:
                if self._serial_service.is_connected:
                    self._serial_service.disconnect()
                    time.sleep(0.5)
                success, info = self._flasher.flash(port, file_path)
                logger.info(f"Background flashing complete. Status: {success}, Info: {info}")
            except Exception as e:
                logger.error(f"Error in background flashing thread: {e}")
                on_finished(False, f"Internal flashing thread error: {str(e)}")

        flashing_thread = threading.Thread(target=run_flash_async, name="FlasherThread", daemon=True)
        flashing_thread.start()
        
        return {"status": "success", "message": "Flashing started in background"}

    # --- MacroMixin Endpoints ---
    @safe_api
    def execute_macro(self, macro_data):
        if macro_data.get("type") == "window_service":
            action = macro_data.get("action")
            if action == "minimize":
                self._window_control_service.minimize_windows()
            elif action == "restore_all":
                self._window_control_service.restore_windows()
            return {"status": "success"}
        self._macro_execution_service.execute_macro(macro_data)
        return {"status": "success"}

    @safe_api
    def start_macro_recording(self):
        if not self._macro_recording_service._ui_bridge:
            self._macro_recording_service.set_ui_bridge(self._ui_bridge)
        self._macro_recording_service.start_recording()
        return {"status": "success"}

    @safe_api
    def stop_macro_recording(self):
        self._macro_recording_service.stop_recording()
        return {"status": "success"}

    def _execute_macro_by_name(self, macro_name, profile_data):
        macro_data = profile_data.get("macros", {}).get(macro_name)
        if not macro_data:
            for p_name, p_data in self._profiles.get("profiles", {}).items():
                if p_data.get("macros") and macro_name in p_data["macros"]:
                    macro_data = p_data["macros"][macro_name]
                    break
        if macro_data:
            self.execute_macro(macro_data)
        else:
            system_macros = self._get_system_macros()
            if macro_name in system_macros:
                self.execute_macro(system_macros[macro_name])

    def _resolve_macro_for_execution(self, macro_name):
        profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
        macro_data = profile_data.get("macros", {}).get(macro_name)
        if not macro_data:
            for p_name, p_data in self._profiles.get("profiles", {}).items():
                if p_data.get("macros") and macro_name in p_data["macros"]:
                    macro_data = p_data["macros"][macro_name]
                    break
        if macro_data:
            return macro_data
        system_macros = self._get_system_macros()
        return system_macros.get(macro_name)

    def _get_system_macros(self):
        return {
            "Copy": {"name": "Copy", "sequence": ["Ctrl", "C"]},
            "Paste": {"name": "Paste", "sequence": ["Ctrl", "V"]},
            "Cut": {"name": "Cut", "sequence": ["Ctrl", "X"]},
            "Select All": {"name": "Select All", "sequence": ["Ctrl", "A"]},
            "Undo": {"name": "Undo", "sequence": ["Ctrl", "Z"]},
            "Redo": {"name": "Redo", "sequence": ["Ctrl", "Y"]},
            "Save": {"name": "Save", "sequence": ["Ctrl", "S"]},
            "Find": {"name": "Find", "sequence": ["Ctrl", "F"]},
            "Replace": {"name": "Replace", "sequence": ["Ctrl", "H"]},
            "New Tab": {"name": "New Tab", "sequence": ["Ctrl", "T"]},
            "Close Tab": {"name": "Close Tab", "sequence": ["Ctrl", "W"]},
            "Switch Tab": {"name": "Switch Tab", "sequence": ["Ctrl", "Tab"]},
            "Refresh": {"name": "Refresh", "sequence": ["F5"]},
            "Minimize Window": {"name": "Minimize Window", "type": "window_service", "action": "minimize"},
            "Restore Windows": {"name": "Restore Windows", "type": "window_service", "action": "restore_all"},
            "Volume Up": {"name": "Volume Up", "sequence": ["volup"]},
            "Volume Down": {"name": "Volume Down", "sequence": ["voldown"]},
            "Mute": {"name": "Mute", "sequence": ["volumemute"]},
            "Play/Pause": {"name": "Play/Pause", "sequence": ["media_play_pause"]},
            "Next Track": {"name": "Next Track", "sequence": ["media_next"]},
            "Previous Track": {"name": "Previous Track", "sequence": ["media_previous"]},
        }

    def _execute_knob_callback(self, command: str):
        profile_data = self._profiles.get("profiles", {}).get(self._current_profile_name, {})
        current_mode = self._knob_controller.mode
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
        try:
            if message in ["KNOB_LEFT", "KNOB_RIGHT", "KNOB_PRESS"]:
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
                except (ValueError, IndexError):
                    return
                macro_name = profile_data.get("keys", {}).get(str(idx))
            if macro_name:
                if self._macro_recording_service._recording:
                    # Suppress macro execution on PC during recording
                    pass
                else:
                    self._execute_macro_by_name(macro_name, profile_data)
        except Exception as e:
            logger.error(f"Error handling serial command '{message}': {e}", exc_info=True)
            
    @safe_api
    def link_app_to_profile(self, profile_name, app_exe):
        if not app_exe:
            return {"status": "error", "message": "Application name cannot be empty"}
        rules = self._config.get("auto_switching", {}).get("rules", {})
        app_key = app_exe.lower()
        rules[app_key] = profile_name
        if "auto_switching" not in self._config:
            self._config["auto_switching"] = {"enabled": True, "rules": rules}
        else:
            self._config["auto_switching"]["rules"] = rules
        self._save_config()
        self._profile_switcher.update_config(self._config)
        return {"status": "success", "message": f"Linked {app_exe} to {profile_name}"}

    @safe_api
    def get_linked_app(self, profile_name):
        rules = self._config.get("auto_switching", {}).get("rules", {})
        linked_apps = [app for app, prof in rules.items() if prof == profile_name]
        return {"status": "success", "data": linked_apps}

    @safe_api
    def get_active_processes(self):
        apps = self._profile_switcher.get_active_windows()
        return {"status": "success", "data": apps}

    @safe_api
    def unlink_app_from_profile(self, profile_name):
        rules = self._config.get("auto_switching", {}).get("rules", {})
        apps_to_remove = [app for app, prof in rules.items() if prof == profile_name]
        if not apps_to_remove:
            return {"status": "success", "message": "No apps linked to this profile"}
        for app in apps_to_remove:
            del rules[app]
        self._save_config()
        self._profile_switcher.update_config(self._config)
        return {"status": "success", "message": f"Unlinked {len(apps_to_remove)} apps"}
