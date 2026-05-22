import sys
import logging
import os
import threading
import time
from pathlib import Path
import webview
from PIL import Image, ImageDraw
import pystray
from .api import Api
from .utils.webview2_bootstrapper import ensure_webview2_runtime
import win32gui
import win32con
import win32api
import win32event
import winerror

logger = logging.getLogger(__name__)

def create_icon(connected=False):
    icon_path = Path(__file__).parent.parent / "Icon" / "Logo.png"
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

    # Fallback
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.rectangle((0, 0, width-1, height-1), outline="white", width=2)
    dc.rectangle((24, 24, 40, 40), fill="white")
    status_color = (0, 255, 0) if connected else (128, 128, 128)
    margin = 8
    dot_radius = 8
    dc.ellipse([width - margin - dot_radius*2, height - margin - dot_radius*2, 
                width - margin, height - margin], fill=status_color)
    
    return image

def run_tray(api, window):
    def on_open(icon, item):
        restore_window(window)

    def on_quit(icon, item):
        shutdown_application(api, window, icon)

    icon = pystray.Icon("Overcontrol", create_icon(), "Overcontrol", menu=pystray.Menu(
        pystray.MenuItem("Open", on_open),
        pystray.MenuItem("Quit", on_quit)
    ))
    
    api.tray_icon = icon 
    icon.run()

def refresh_tray(api):
    """Dynamically update tray icon and menu based on connection status."""
    if not api.tray_icon:
        return
        
    try:
        is_connected = api.is_connected()
        api.tray_icon.icon = create_icon(connected=is_connected)
        # Use window from api if available
        window = getattr(api, '_window', None)
        api.tray_icon.menu = create_tray_menu(api, window)
    except Exception as e:
        logger.error(f"Error refreshing tray: {e}")

def apply_window_styles(title):
    try:
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            # Get current style
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            # Add minimize box and system menu to allow taskbar interaction
            style |= win32con.WS_MINIMIZEBOX | win32con.WS_SYSMENU
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
            
            # Force frame update to prevent black screen issues
            # We get the current rect and set it again to force a true redraw
            rect = win32gui.GetWindowRect(hwnd)
            x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
            
            win32gui.SetWindowPos(hwnd, 0, x, y, w, h, 
                win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
                
            print(f"Applied window styles and forced redraw for '{title}'")
        else:
            print(f"Window '{title}' not found for style application")
    except Exception as e:
        logger.error(f"Error applying window styles: {e}")

# --- Tray Handlers & Menu Logic (Global) ---

def restore_window(window):
    window.restore()
    window.show()
    # Force redraw to fix black screen when restoring from tray
    try:
        hwnd = win32gui.FindWindow(None, "Overcontrol")
        if hwnd:
            win32gui.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | 
                win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW
            )
    except Exception as e:
        print(f"Error restoring window: {e}")

def on_tray_double_click_handler(icon, item, window):
    current_time = time.time()
    last_click = getattr(on_tray_double_click_handler, 'last_click_time', 0)
    
    if current_time - last_click < 0.5:
        restore_window(window)
        on_tray_double_click_handler.last_click_time = 0
        return
        
    on_tray_double_click_handler.last_click_time = current_time

def on_serial_connect(icon, item, api):
    """Automatically scan and connect to the first available port, matching UI button behavior."""
    try:
        ports = api.get_serial_ports()
        if ports:
            port = ports[0][0]
            print(f"Tray: Auto-connecting to {port}")
            api.connect_serial(port)
        else:
            if hasattr(api, '_send_toast_notification'):
                api._send_toast_notification("Connection Failed", "No devices found")
    except Exception as e:
        logger.error(f"Tray: Error during auto-connect: {e}")

def on_serial_disconnect(icon, item, api):
    print("Tray: Disconnecting serial")
    api.disconnect_serial()

def shutdown_application(api, window, icon=None):
    """Centralized shutdown logic to ensure all components close properly."""
    try:
        print("Shutting down application...")
        
        # 1. Stop background services
        if hasattr(api, '_profile_switcher'):
            api._profile_switcher.stop()
            
        if hasattr(api, '_serial_service'):
            api._serial_service.disconnect()
            
        if hasattr(api, '_ui_bridge'):
            api._ui_bridge.shutdown()
            
        # 2. Stop tray icon
        # Use explicit visibility toggle and internal stop
        target_icon = icon if icon else getattr(api, 'tray_icon', None)
        if target_icon:
            try:
                target_icon.visible = False
                target_icon.stop()
            except Exception:
                pass
            
        # 3. Destroy window
        if window:
            window.destroy()
            
        # Small delay to allow the Windows Tray to receive the 'remove' message
        # before the process is killed
        import time
        time.sleep(0.2)
            
        # 4. Exit immediately to prevent tracebacks from child threads
        os._exit(0)
    except Exception as e:
        print(f"Error during shutdown: {e}")
        os._exit(1)

def on_tray_quit(icon, item, api, window):
    shutdown_application(api, window, icon)

def on_profile_select(icon, item, api):
    profile_name = str(item)
    print(f"Tray: Switching to profile {profile_name}")
    result = api.set_active_profile(profile_name, is_auto=False)
    if result.get("status") == "success":
        if hasattr(api, '_send_toast_notification'):
            api._send_toast_notification(f"Active Profile: {profile_name}", "Switched via System Tray")
        if api._window:
            import json
            safe_name = json.dumps(profile_name)
            api._ui_bridge.evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")

def create_tray_menu(api_instance, window):
    items = [
        pystray.MenuItem("Activate", lambda icon, item: on_tray_double_click_handler(icon, item, window), default=True, visible=False),
        pystray.MenuItem("Open", lambda icon, item: restore_window(window)),
    ]

    # Profiles Section (Moved up)
    try:
        profiles_dict = api_instance._profiles.get("profiles", {})
        if profiles_dict:
            profile_items = []
            for p_name in sorted(profiles_dict.keys()):
                def make_profile_item(name):
                    def is_checked(item):
                        return api_instance._current_profile_name == name
                    return pystray.MenuItem(name, lambda icon, item: on_profile_select(icon, item, api_instance), checked=is_checked, radio=True)
                
                profile_items.append(make_profile_item(p_name))
            items.append(pystray.MenuItem("Profiles", pystray.Menu(*profile_items)))
    except Exception as e:
        print(f"Error creating profile menu: {e}")

    items.append(pystray.Menu.SEPARATOR)

    # --- Simple Connectivity Toggle (Matches UI Button) ---
    try:
        is_connected = api_instance.is_connected()
    except Exception as e:
        print(f"Error checking connection status: {e}")
        is_connected = False

    if is_connected:
        items.append(pystray.MenuItem("Disconnect", lambda icon, item: on_serial_disconnect(icon, item, api_instance)))
    else:
        items.append(pystray.MenuItem("Connect", lambda icon, item: on_serial_connect(icon, item, api_instance)))

    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("Quit", lambda icon, item: on_tray_quit(icon, item, api_instance, window)))
    return pystray.Menu(*items)

def tray_loop(api):
    """Background monitor to refresh tray and check for hardware disconnection."""
    previous_ports = set()
    first_run = True
    
    while True:
        try:
            connected = api.is_connected()
            ports = api.get_serial_ports()
            current_ports = {p[0] for p in ports}
            
            new_ports = current_ports - previous_ports
            previous_ports = current_ports
            
            if not connected:
                # Disconnected: Scan only NEW ports for Monolith (or generic RP2040) automatically
                if not first_run:
                    monolith = next((p for p in ports if p[0] in new_ports and any(s in (p[1] + str(p[2] if len(p) > 2 else '')).lower() for s in ['monolith', '2e8a:0002', '2e8a:0003'])), None)
                    
                    if monolith:
                        logger.info(f"Tray Monitor: Found NEW device on {monolith[0]}, attempting auto-connect")
                        api.connect_serial(monolith[0])
                
                refresh_tray(api)
            else:
                # Connected: Verify the physical port still exists
                if not api._serial_service.check_physical_connection_health():
                    logger.warning("Tray Monitor: Detected physical device disconnection")
                    refresh_tray(api)
                    
            first_run = False
        except Exception as e:
            logger.error(f"Error in tray loop: {e}")
        time.sleep(2)

def main():
    # Single Instance Check using Mutex
    # Use a unique name for the mutex (Global\\ ensures it works across sessions if needed)
    app_mutex = win32event.CreateMutex(None, False, "Global\\OvercontrolMutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("Another instance is already running. Brining it to focus...")
        hwnd = win32gui.FindWindow(None, "Overcontrol")
        if hwnd:
            # If minimized, restore it
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetForegroundWindow(hwnd)
        sys.exit(0)

    # Check for WebView2 Runtime before starting
    # This ensures the application can run even if WebView2 is not pre-installed
    print("Checking WebView2 Runtime...")
    if not ensure_webview2_runtime(interactive=False):
        print("ERROR: WebView2 Runtime is required but not available.")
        print("Please install it from: https://developer.microsoft.com/microsoft-edge/webview2/")
        input("Press Enter to exit...")
        sys.exit(1)
    
    api = Api()

    # Force dark theme for system tray menu
    try:
        import ctypes
        # SetPreferredAppMode(2) - Force dark mode for context menus
        # This is an unofficial Windows API but widely used for dark mode support
        uxtheme = ctypes.windll.uxtheme
        uxtheme.SetPreferredAppMode(2)
        # FlushMenuThemes() ensures the setting is applied immediately
        uxtheme.FlushMenuThemes()
    except Exception as e:
        logger.warning(f"Could not set dark theme for tray menu: {e}")
    
    # Path to index.html
    assets_dir = Path(__file__).parent / "assets"
    index_path = assets_dir / "index.html"
    
    if not index_path.exists():
        logger.error(f"Error: {index_path} not found")
        assets_dir.mkdir(parents=True, exist_ok=True)
        
    # Determine startup state
    start_minimized = False
    if "--minimized" in sys.argv:
        start_minimized = True
        print("Starting minimized to tray...")

    # Create a transparent icon for the window
    import tempfile
    transparent_icon_path = os.path.join(tempfile.gettempdir(), 'transparent_overcontrol.ico')
    try:
        # Create it always to be sure
        img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        img.save(transparent_icon_path, format='ICO')
    except Exception as e:
        logger.warning(f"Could not create transparent icon: {e}")
        transparent_icon_path = None

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
    
    # Tray Logic

    # Initialize icon with dynamic menu
    tray_icon = pystray.Icon("Overcontrol", create_icon(connected=api.is_connected()), "Overcontrol", menu=create_tray_menu(api, window))
    api.tray_icon = tray_icon
    api.set_tray_update_callback(lambda: refresh_tray(api))
    
    # Start tray icon in its own thread
    tray_thread = threading.Thread(target=tray_icon.run)
    tray_thread.daemon = True
    tray_thread.start()
    
    # Start monitor thread for auto-detection
    monitor_thread = threading.Thread(target=tray_loop, args=(api,))
    monitor_thread.daemon = True
    monitor_thread.start()

    def on_closing():
        if api.tray_enabled:
            window.hide()
            return False 
        
        shutdown_application(api, window)
        return True 

    # Startup Style Application
    def startup_style_application():
        import time
        # Wait for window to be created
        max_retries = 20
        hwnd = 0
        for _ in range(max_retries):
            hwnd = win32gui.FindWindow(None, "Overcontrol")
            if hwnd:
                break
            time.sleep(0.5)
            
        if not hwnd:
            print("Could not find window for style application")
            return

        print(f"Found window HWND: {hwnd}")
        
        try:
            # 0. Remove Title Text
            win32gui.SetWindowText(hwnd, "")
            
            # 0.5 Update Icon
            try:
                import tempfile
                logo_path = Path(__file__).parent.parent / "Icon" / "Logo.png"
                icon_path = os.path.join(tempfile.gettempdir(), 'overcontrol_logo.ico')
                if os.path.exists(logo_path) and not os.path.exists(icon_path):
                    img = Image.open(logo_path)
                    img.save(icon_path, format='ICO')
                elif not os.path.exists(logo_path):
                    if not os.path.exists(icon_path):
                        img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
                        img.save(icon_path, format='ICO')
                
                h_icon_small = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXSMICON), win32api.GetSystemMetrics(win32con.SM_CYSMICON), win32con.LR_LOADFROMFILE)
                if h_icon_small: win32gui.SendMessage(hwnd, 0x0080, 0, h_icon_small)
                
                h_icon_big = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, win32api.GetSystemMetrics(win32con.SM_CXICON), win32api.GetSystemMetrics(win32con.SM_CYICON), win32con.LR_LOADFROMFILE)
                if h_icon_big: win32gui.SendMessage(hwnd, 0x0080, 1, h_icon_big)
            except Exception as e:
                print(f"Icon error: {e}")

            # 1. Dark Mode
            try:
                import ctypes
                enable = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enable), ctypes.sizeof(enable))
                color = 0x001a1a1a
                color_ref = ctypes.c_int(color)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color_ref), ctypes.sizeof(color_ref))
            except Exception as e:
                 print(f"Dark mode error: {e}")

            # 2. Window Style
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style |= (win32con.WS_SYSMENU | win32con.WS_MINIMIZEBOX)
            style &= ~(win32con.WS_MAXIMIZEBOX | win32con.WS_THICKFRAME)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
            
            # 3. Handle Visibility Based on Startup Flag
            if start_minimized:
                # Explicitly Hide
                print("Hiding window for startup...")
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                # Apply frame change without showing
                win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
            else:
                # Force Show and Redraw
                win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)
                
            print("Startup styles applied successfully")

        except Exception as e:
            logger.error(f"Error applying styles: {e}")
    
    # Start style thread immediately 
    style_thread = threading.Thread(target=startup_style_application)
    style_thread.daemon = True
    style_thread.start()

    window.events.closing += on_closing
    
    webview.start(debug=False)
    sys.exit(0)

if __name__ == "__main__":
    main()
