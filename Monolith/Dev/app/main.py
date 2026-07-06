import sys
import os
import time
import logging
import threading
import json
import ctypes
from pathlib import Path
from PIL import Image, ImageDraw
import pystray
import webview

import win32gui
import win32con
import win32api
import win32event
import winerror

# Import our custom consolidated services/utils
from .api import Api, get_ui_bridge

logger = logging.getLogger(__name__)
_app_mutex = None

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path

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
        win32gui.SetWindowText(hwnd, "")
        
        # Apply window icon
        import tempfile
        logo_path = get_resource_path_func("Icon/Logo.png")
        icon_path = os.path.join(tempfile.gettempdir(), 'overcontrol_logo.ico')
        
        if logo_path.exists() and not os.path.exists(icon_path):
            try:
                img = Image.open(logo_path)
                img.save(icon_path, format='ICO')
            except Exception as e:
                logger.warning(f"Could not convert PNG logo to ICO: {e}")
                
        if os.path.exists(icon_path):
            h_icon_small = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXSMICON), win32api.GetSystemMetrics(win32con.SM_CYSMICON), win32con.LR_LOADFROMFILE)
            if h_icon_small:
                win32gui.SendMessage(hwnd, 0x0080, 0, h_icon_small)
            
            h_icon_big = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXICON), win32api.GetSystemMetrics(win32con.SM_CYICON), win32con.LR_LOADFROMFILE)
            if h_icon_big:
                win32gui.SendMessage(hwnd, 0x0080, 1, h_icon_big)
        
        # Apply immersive dark mode
        enable = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enable), ctypes.sizeof(enable))
        color_ref = ctypes.c_int(0x001a1a1a)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color_ref), ctypes.sizeof(color_ref))
        
        # Modify window styles
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style |= (win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX)
        style &= ~(win32con.WS_MAXIMIZEBOX | win32con.WS_THICKFRAME)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        
        if start_minimized:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
        else:
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
            
        logger.info("Startup window styles applied successfully")
    except Exception as e:
        logger.error(f"Error executing startup window styles: {e}")

class TrayManager:
    def __init__(self, api, window):
        self.api = api
        self.window = window
        self.tray_icon = None
        self.last_click_time = 0
        
    def create_icon_image(self, connected=False):
        icon_path = get_resource_path("Icon/Logo.png")
        try:
            if icon_path.exists():
                base = Image.open(icon_path).convert("RGBA")
                base = base.resize((64, 64), Image.Resampling.LANCZOS)
                image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                image.paste(base, (0, 0))
                dc = ImageDraw.Draw(image)
                status_color = (0, 255, 0, 255) if connected else (128, 128, 128, 255)
                margin = 4
                dot_radius = 6
                width, height = 64, 64
                dc.ellipse([width - margin - dot_radius*2, height - margin - dot_radius*2, 
                            width - margin, height - margin], fill=status_color)
                return image
        except Exception as e:
            logger.error(f"Error loading icon: {e}")

        # Fallback drawing
        width, height = 64, 64
        image = Image.new('RGB', (width, height), (0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0, 0, width-1, height-1), outline="white", width=2)
        dc.rectangle((24, 24, 40, 40), fill="white")
        status_color = (0, 255, 0) if connected else (128, 128, 128)
        margin, dot_radius = 8, 8
        dc.ellipse([width - margin - dot_radius*2, height - margin - dot_radius*2, 
                    width - margin, height - margin], fill=status_color)
        return image

    def run(self):
        def on_open(icon, item):
            restore_window(self.window)
        def on_quit(icon, item):
            self.shutdown_application(icon)

        self.tray_icon = pystray.Icon(
            "Overcontrol", 
            self.create_icon_image(connected=self.api.is_connected()), 
            "Overcontrol", 
            menu=pystray.Menu(
                pystray.MenuItem("Open", on_open),
                pystray.MenuItem("Quit", on_quit)
            )
        )
        self.api.tray_icon = self.tray_icon
        self.tray_icon.run()

    def refresh(self):
        if not self.tray_icon:
            return
        try:
            connected = self.api.is_connected()
            self.tray_icon.icon = self.create_icon_image(connected=connected)
            self.tray_icon.menu = self.create_tray_menu()
        except Exception as e:
            logger.error(f"Error refreshing tray: {e}")

    def on_tray_double_click(self, icon, item):
        current_time = time.time()
        if current_time - self.last_click_time < 0.5:
            restore_window(self.window)
            self.last_click_time = 0
            return
        self.last_click_time = current_time

    def on_serial_connect(self, icon, item):
        try:
            ports = self.api.get_serial_ports()
            if not ports:
                self.api._send_toast_notification("Connection Failed", "No devices found")
                return
            port = ports[0][0]
            logger.info(f"Tray: Auto-connecting to {port}")
            self.api.connect_serial(port)
        except Exception as e:
            logger.error(f"Tray: Error during auto-connect: {e}")

    def on_serial_disconnect(self, icon, item):
        logger.info("Tray: Disconnecting serial")
        self.api.disconnect_serial()

    def on_profile_select(self, icon, item):
        profile_name = str(item)
        logger.info(f"Tray: Switching to profile {profile_name}")
        result = self.api.set_active_profile(profile_name, is_auto=False)
        if result.get("status") != "success":
            return
        self.api._send_toast_notification(f"Active Profile: {profile_name}", "Switched via System Tray")
        if self.api._window:
            safe_name = json.dumps(profile_name)
            get_ui_bridge().evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")

    def create_tray_menu(self):
        items = [
            pystray.MenuItem("Activate", self.on_tray_double_click, default=True, visible=False),
            pystray.MenuItem("Open", lambda icon, item: restore_window(self.window)),
        ]

        try:
            profiles_dict = self.api._profiles.get("profiles", {})
            if profiles_dict:
                profile_items = []
                for p_name in sorted(profiles_dict.keys()):
                    def make_profile_item(name):
                        return pystray.MenuItem(
                            name, 
                            lambda icon, item: self.on_profile_select(icon, item), 
                            checked=lambda item: self.api._current_profile_name == name, 
                            radio=True
                        )
                    profile_items.append(make_profile_item(p_name))
                items.append(pystray.MenuItem("Profiles", pystray.Menu(*profile_items)))
        except Exception as e:
            logger.error(f"Error creating profile menu in tray: {e}")

        items.append(pystray.Menu.SEPARATOR)
        is_connected = self.api.is_connected()
        if is_connected:
            items.append(pystray.MenuItem("Disconnect", self.on_serial_disconnect))
        else:
            items.append(pystray.MenuItem("Connect", self.on_serial_connect))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", lambda icon, item: self.shutdown_application(icon)))
        return pystray.Menu(*items)

    def shutdown_application(self, icon=None):
        try:
            logger.info("Shutting down application...")
            self.api.tray_loop_running = False
            
            if hasattr(self.api, '_macro_recording_service'):
                self.api._macro_recording_service.stop_recording(is_emergency=True)
            if hasattr(self.api, '_knob_controller'):
                self.api._knob_controller.finalize_app_switch()
            if hasattr(self.api, '_profile_switcher'):
                self.api._profile_switcher.stop()
            if hasattr(self.api, '_serial_service'):
                self.api._serial_service.disconnect()
            
            get_ui_bridge().shutdown()
                
            target_icon = icon if icon else self.tray_icon
            if target_icon:
                try:
                    target_icon.visible = False
                    target_icon.stop()
                except Exception:
                    pass
                
            if self.window:
                self.window.destroy()
                
            time.sleep(0.2)
            os._exit(0)
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            os._exit(1)

    def monitor_loop(self):
        previous_ports = set()
        first_run = True
        
        while getattr(self.api, 'tray_loop_running', True):
            try:
                connected = self.api.is_connected()
                ports = self.api.get_serial_ports()
                current_ports = {p[0] for p in ports}
                new_ports = current_ports - previous_ports
                previous_ports = current_ports
                
                if not connected:
                    if not first_run:
                        last_port = self.api._serial_service._last_connected_port
                        autoconnect_port = None
                        
                        if last_port and last_port in new_ports:
                            autoconnect_port = last_port
                            logger.info(f"Tray Monitor: Last active port {last_port} reconnected. Attempting auto-connect.")
                        else:
                            monolith = next((p for p in ports if p[0] in new_ports and any(s in (p[1] + str(p[2] if len(p) > 2 else '')).lower() for s in ['monolith', '2e8a:0002', '2e8a:0003', '1209:c550'])), None)
                            if monolith:
                                autoconnect_port = monolith[0]
                                logger.info(f"Tray Monitor: Found NEW device on {monolith[0]}, attempting auto-connect")
                                
                        if autoconnect_port:
                            self.api.connect_serial(autoconnect_port)
                    self.refresh()
                else:
                    if not self.api._serial_service.check_physical_connection_health():
                        logger.warning("Tray Monitor: Detected physical device disconnection")
                        self.refresh()
                first_run = False
            except Exception as e:
                logger.error(f"Error in tray loop: {e}")
            time.sleep(2)

def main():
    single_instance_check("Overcontrol")
    
    api = Api()
    assets_dir = get_resource_path("app/assets")
    index_path = assets_dir / "index.html"
    
    if not index_path.exists():
        logger.error(f"Error: {index_path} not found")
        assets_dir.mkdir(parents=True, exist_ok=True)
        
    start_minimized = "--minimized" in sys.argv

    window = webview.create_window(
        "Overcontrol", 
        url=index_path.as_uri() if index_path.exists() else None,
        js_api=api,
        width=1280,
        height=800,
        resizable=False,
        min_size=(1280, 800),
        background_color='#1a1a1a',
        frameless=False,
        hidden=start_minimized,
        easy_drag=False
    )
    api.set_window(window)

    tray_manager = TrayManager(api, window)
    api.set_tray_update_callback(tray_manager.refresh)
    
    tray_thread = threading.Thread(target=tray_manager.run)
    tray_thread.daemon = True
    tray_thread.start()
    
    monitor_thread = threading.Thread(target=tray_manager.monitor_loop)
    monitor_thread.daemon = True
    monitor_thread.start()

    def on_closing():
        if api.tray_enabled:
            if hasattr(api, '_macro_recording_service'):
                api._macro_recording_service.stop_recording(is_emergency=True)
            window.hide()
            return False 
        tray_manager.shutdown_application()
        return True 

    def on_minimized():
        logger.info("Window minimized: stopping active macro recording")
        if hasattr(api, '_macro_recording_service'):
            api._macro_recording_service.stop_recording(is_emergency=True)

    window.events.minimized += on_minimized
    window.events.closing += on_closing

    style_thread = threading.Thread(
        target=startup_style_application, 
        args=("Overcontrol", start_minimized, get_resource_path)
    )
    style_thread.daemon = True
    style_thread.start()

    webview.start(debug=False)
    sys.exit(0)

if __name__ == "__main__":
    main()
