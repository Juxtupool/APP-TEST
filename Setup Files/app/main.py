import sys
import os
import threading
from pathlib import Path
import webview
from PIL import Image, ImageDraw
import pystray
from .api import Api
from .utils.webview2_bootstrapper import ensure_webview2_runtime

def create_icon():
    # Simple icon: Black background, white "M" or box
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (0, 0, 0))
    dc = ImageDraw.Draw(image)
    # White border
    dc.rectangle((0, 0, width-1, height-1), outline="white", width=2)
    # White dot in center
    dc.rectangle((24, 24, 40, 40), fill="white")
    return image

def run_tray(api, window):
    def on_open(icon, item):
        window.restore()
        window.show()

    def on_quit(icon, item):
        # Proper cleanup sequence instead of os._exit()
        try:
            # Disconnect serial to avoid leaving port locked
            if hasattr(api, '_serial_service'):
                api._serial_service.disconnect()
            
            # Stop UI bridge
            if hasattr(api, '_ui_bridge'):
                api._ui_bridge.shutdown()
            
            # Stop tray icon
            icon.stop()
            
            # Destroy window
            window.destroy()
            
            # Normal exit (allows Python cleanup)
            sys.exit(0)
        except Exception:
            # Fallback emergency exit if cleanup fails
            sys.exit(1)

    icon = pystray.Icon("Macropad Pro", create_icon(), "Macropad Pro", menu=pystray.Menu(
        pystray.MenuItem("Open", on_open),
        pystray.MenuItem("Quit", on_quit)
    ))
    
    api.tray_icon = icon 
    icon.run()


def main():
    # Check for WebView2 Runtime before starting
    # This ensures the application can run even if WebView2 is not pre-installed
    print("Checking WebView2 Runtime...")
    if not ensure_webview2_runtime(interactive=False):
        print("ERROR: WebView2 Runtime is required but not available.")
        print("Please install it from: https://developer.microsoft.com/microsoft-edge/webview2/")
        input("Press Enter to exit...")
        sys.exit(1)
    
    api = Api()
    
    # Path to index.html
    assets_dir = Path(__file__).parent / "assets"
    index_path = assets_dir / "index.html"
    
    if not index_path.exists():
        print(f"Error: {index_path} not found")
        # Create directory if it doesn't exist, just in case
        assets_dir.mkdir(parents=True, exist_ok=True)
        # We will create the file in the next steps
        
    window = webview.create_window(
        "Macropad Pro", 
        url=index_path.as_uri() if index_path.exists() else None,
        js_api=api,
        width=1280,
        height=800,
        resizable=True,
        min_size=(1000, 600),
        background_color='#1a1a1a'
    )
    
    api.set_window(window)
    
    # Tray Logic
    tray_thread = threading.Thread(target=run_tray, args=(api, window))
    tray_thread.daemon = True
    tray_thread.start()

    def on_closing():
        if api.tray_enabled:
            window.hide()
            return False # Prevent close
        return True # Allow close

    window.events.closing += on_closing
    
    webview.start(debug=True)

if __name__ == "__main__":
    main()
