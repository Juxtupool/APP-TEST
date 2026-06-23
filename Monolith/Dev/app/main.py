import sys
import logging
from pathlib import Path
import threading
import webview

# Import our custom decomposed services/utils
from .api import Api
from .utils.webview2_bootstrapper import ensure_webview2_runtime
from .services.window_manager import (
    single_instance_check,
    startup_style_application
)
from .services.tray_manager import TrayManager

logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path

def main():
    # 1. Single Instance Check using Win32 Mutex
    single_instance_check("Overcontrol")

    # 2. Check for WebView2 Runtime before starting
    print("Checking WebView2 Runtime...")
    if not ensure_webview2_runtime(interactive=False):
        print("ERROR: WebView2 Runtime is required but not available.")
        print("Please install it from: https://developer.microsoft.com/microsoft-edge/webview2/")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # 3. Create core API
    api = Api()

    # 4. Resolve HTML assets path
    assets_dir = get_resource_path("app/assets")
    index_path = assets_dir / "index.html"
    if not index_path.exists():
        logger.error(f"Error: {index_path} not found")
        assets_dir.mkdir(parents=True, exist_ok=True)
        
    start_minimized = "--minimized" in sys.argv

    # 5. Initialize Webview window
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

    # 6. Initialize TrayManager service
    tray_manager = TrayManager(api, window, get_resource_path)
    api.set_tray_update_callback(tray_manager.refresh)
    
    # Start tray icon in its own thread
    tray_thread = threading.Thread(target=tray_manager.run)
    tray_thread.daemon = True
    tray_thread.start()
    
    # Start monitor thread for hardware/port auto-detection
    monitor_thread = threading.Thread(target=tray_manager.monitor_loop)
    monitor_thread.daemon = True
    monitor_thread.start()

    # 7. Register window closing hooks
    def on_closing():
        if api.tray_enabled:
            if hasattr(api, '_macro_recording_service'):
                try:
                    api._macro_recording_service.stop_recording(is_emergency=True)
                except Exception as e:
                    logger.error(f"Error stopping macro recording on close: {e}")
            window.hide()
            return False 
        tray_manager.shutdown_application()
        return True 

    # 8. Register window minimize hooks to stop recording
    def on_minimized():
        logger.info("Window minimized: stopping active macro recording")
        if hasattr(api, '_macro_recording_service'):
            try:
                api._macro_recording_service.stop_recording(is_emergency=True)
            except Exception as e:
                logger.error(f"Error stopping macro recording on minimize: {e}")

    window.events.minimized += on_minimized
    window.events.closing += on_closing

    # 9. Start asynchronous thread to apply win32 framing window styles
    style_thread = threading.Thread(
        target=startup_style_application, 
        args=("Overcontrol", start_minimized, get_resource_path)
    )
    style_thread.daemon = True
    style_thread.start()

    # 10. Run PyWebView main loop
    webview.start(debug=False)
    sys.exit(0)

if __name__ == "__main__":
    main()
