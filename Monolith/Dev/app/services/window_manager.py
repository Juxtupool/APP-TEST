import sys
import os
import logging
import ctypes
import time
from pathlib import Path
from PIL import Image
import win32gui
import win32con
import win32api
import win32event
import winerror

logger = logging.getLogger(__name__)

# Keep mutex alive
_app_mutex = None

def single_instance_check(title: str = "Overcontrol"):
    """Check if another instance is already running using Win32 Mutex."""
    global _app_mutex
    _app_mutex = win32event.CreateMutex(None, False, "Global\\OvercontrolMutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        logger.warning("Another instance of the application is already running.")
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
        sys.exit(0)

def apply_window_styles(title: str):
    """Enable minimize functionality and focus layout changes on target HWND."""
    try:
        hwnd = win32gui.FindWindow(None, title)
        if not hwnd:
            logger.warning(f"Window '{title}' not found for style application")
            return
            
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style |= win32con.WS_MINIMIZEBOX | win32con.WS_SYSMENU
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        
        # Force frame update to redraw correctly
        rect = win32gui.GetWindowRect(hwnd)
        x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        win32gui.SetWindowPos(hwnd, 0, x, y, w, h, 
            win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
        logger.info(f"Applied window styles and forced redraw for '{title}'")
    except Exception as e:
        logger.error(f"Error applying window styles: {e}")

def restore_window(window, title: str = "Overcontrol"):
    """Restore window from tray and redraw frame to prevent black screens."""
    window.restore()
    window.show()
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            win32gui.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | 
                win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW
            )
    except Exception as e:
        logger.error(f"Error restoring window: {e}")

def _apply_dark_mode(hwnd):
    """Enable Win11/Win10 dark mode titlebar window styles."""
    try:
        enable = ctypes.c_int(1)
        # 20: DWMWA_USE_IMMERSIVE_DARK_MODE
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enable), ctypes.sizeof(enable))
        # 35: DWMWA_CAPTION_COLOR
        color = 0x001a1a1a
        color_ref = ctypes.c_int(color)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color_ref), ctypes.sizeof(color_ref))
    except Exception as e:
        logger.warning(f"Failed to set DWM dark mode attribute: {e}")

def _apply_window_icon(hwnd, get_resource_path_func):
    """Set custom window icons from project resource path."""
    import tempfile
    logo_path = get_resource_path_func("Icon/Logo.png")
    icon_path = os.path.join(tempfile.gettempdir(), 'overcontrol_logo.ico')
    
    if not logo_path.exists():
        if not os.path.exists(icon_path):
            img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
            img.save(icon_path, format='ICO')
    elif not os.path.exists(icon_path):
        try:
            img = Image.open(logo_path)
            img.save(icon_path, format='ICO')
        except Exception as e:
            logger.warning(f"Could not convert PNG logo to ICO: {e}")
            
    try:
        if os.path.exists(icon_path):
            h_icon_small = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXSMICON), win32api.GetSystemMetrics(win32con.SM_CYSMICON), win32con.LR_LOADFROMFILE)
            if h_icon_small:
                win32gui.SendMessage(hwnd, 0x0080, 0, h_icon_small)
            
            h_icon_big = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXICON), win32api.GetSystemMetrics(win32con.SM_CYICON), win32con.LR_LOADFROMFILE)
            if h_icon_big:
                win32gui.SendMessage(hwnd, 0x0080, 1, h_icon_big)
    except Exception as e:
        logger.error(f"Error setting window icons: {e}")

def startup_style_application(title: str, start_minimized: bool, get_resource_path_func):
    """Initialize styling hooks for frameless layout configuration on startup."""
    hwnd = 0
    for _ in range(20):
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            break
        time.sleep(0.5)
        
    if not hwnd:
        logger.error("Could not find window HWND for style initialization")
        return

    try:
        # 1. Remove Title Text
        win32gui.SetWindowText(hwnd, "")
        
        # 2. Update Icon
        _apply_window_icon(hwnd, get_resource_path_func)
        
        # 3. Apply Dark Mode
        _apply_dark_mode(hwnd)
        
        # 4. Modify Window style flags
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style |= (win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX)
        style &= ~(win32con.WS_MAXIMIZEBOX | win32con.WS_THICKFRAME)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        
        # 5. Handle Visibility
        if start_minimized:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
        else:
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
            
        logger.info("Startup window styles applied successfully")
    except Exception as e:
        logger.error(f"Error executing startup window styles: {e}")
