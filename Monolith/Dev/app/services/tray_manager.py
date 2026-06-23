import os
import sys
import time
import logging
import json
from PIL import Image, ImageDraw
import pystray
from app.services.window_manager import restore_window

logger = logging.getLogger(__name__)

class TrayManager:
    def __init__(self, api, window, get_resource_path_func):
        self.api = api
        self.window = window
        self.get_resource_path = get_resource_path_func
        self.tray_icon = None
        self.last_click_time = 0
        
    def create_icon_image(self, connected=False):
        """Create tray icon image using the logo or fallback generator."""
        icon_path = self.get_resource_path("Icon/Logo.png")
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

    def run(self):
        """Initialize and run the pystray Icon block."""
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
        """Dynamically update tray icon image and menus."""
        if not self.tray_icon:
            return
        try:
            connected = self.api.is_connected()
            self.tray_icon.icon = self.create_icon_image(connected=connected)
            self.tray_icon.menu = self.create_tray_menu()
        except Exception as e:
            logger.error(f"Error refreshing tray: {e}")

    def on_tray_double_click(self, icon, item):
        """Handle tray icon double click and restore UI window."""
        current_time = time.time()
        if current_time - self.last_click_time < 0.5:
            restore_window(self.window)
            self.last_click_time = 0
            return
        self.last_click_time = current_time

    def on_serial_connect(self, icon, item):
        """Scan and automatically connect to target serial port."""
        try:
            ports = self.api.get_serial_ports()
            if not ports:
                if hasattr(self.api, '_send_toast_notification'):
                    self.api._send_toast_notification("Connection Failed", "No devices found")
                return
            port = ports[0][0]
            logger.info(f"Tray: Auto-connecting to {port}")
            self.api.connect_serial(port)
        except Exception as e:
            logger.error(f"Tray: Error during auto-connect: {e}")

    def on_serial_disconnect(self, icon, item):
        """Disconnect active serial session."""
        logger.info("Tray: Disconnecting serial")
        self.api.disconnect_serial()

    def on_profile_select(self, icon, item):
        """Handle dynamic profile switching from tray menu select."""
        profile_name = str(item)
        logger.info(f"Tray: Switching to profile {profile_name}")
        result = self.api.set_active_profile(profile_name, is_auto=False)
        if result.get("status") != "success":
            return
        if hasattr(self.api, '_send_toast_notification'):
            self.api._send_toast_notification(f"Active Profile: {profile_name}", "Switched via System Tray")
        if self.api._window:
            safe_name = json.dumps(profile_name)
            self.api._ui_bridge.evaluate_js_safe(f"window.onAutoProfileSwitch({safe_name})")

    def create_tray_menu(self):
        """Compile complete tray items and submenus."""
        items = [
            pystray.MenuItem("Activate", self.on_tray_double_click, default=True, visible=False),
            pystray.MenuItem("Open", lambda icon, item: restore_window(self.window)),
        ]

        # Profiles Section
        try:
            profiles_dict = self.api._profiles.get("profiles", {})
            if profiles_dict:
                profile_items = []
                for p_name in sorted(profiles_dict.keys()):
                    def make_profile_item(name):
                        def is_checked(item):
                            return self.api._current_profile_name == name
                        return pystray.MenuItem(
                            name, 
                            lambda icon, item: self.on_profile_select(icon, item), 
                            checked=is_checked, 
                            radio=True
                        )
                    profile_items.append(make_profile_item(p_name))
                items.append(pystray.MenuItem("Profiles", pystray.Menu(*profile_items)))
        except Exception as e:
            logger.error(f"Error creating profile menu in tray: {e}")

        items.append(pystray.Menu.SEPARATOR)

        # Connect/Disconnect Toggle
        try:
            is_connected = self.api.is_connected()
        except Exception as e:
            logger.error(f"Error checking connection status for tray: {e}")
            is_connected = False

        if is_connected:
            items.append(pystray.MenuItem("Disconnect", self.on_serial_disconnect))
        else:
            items.append(pystray.MenuItem("Connect", self.on_serial_connect))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", lambda icon, item: self.shutdown_application(icon)))
        
        return pystray.Menu(*items)

    def shutdown_application(self, icon=None):
        """Tear down all subsystems and cleanly close execution process."""
        try:
            logger.info("Shutting down application...")
            
            # Stop tray loop
            self.api.tray_loop_running = False
            
            # 1. Stop background services
            if hasattr(self.api, '_macro_recording_service'):
                try:
                    self.api._macro_recording_service.stop_recording(is_emergency=True)
                except Exception as e:
                    logger.error(f"Error stopping macro recording on shutdown: {e}")

            if hasattr(self.api, '_knob_controller'):
                try:
                    self.api._knob_controller.finalize_app_switch()
                except Exception as e:
                    logger.error(f"Error finalizing app switcher key holds: {e}")

            if hasattr(self.api, '_profile_switcher'):
                self.api._profile_switcher.stop()
                
            if hasattr(self.api, '_serial_service'):
                self.api._serial_service.disconnect()
                
            if hasattr(self.api, '_ui_bridge'):
                self.api._ui_bridge.shutdown()
                
            # 2. Stop tray icon
            target_icon = icon if icon else self.tray_icon
            if target_icon:
                try:
                    target_icon.visible = False
                    target_icon.stop()
                except Exception:
                    pass
                
            # 3. Destroy window
            if self.window:
                self.window.destroy()
                
            time.sleep(0.2)
            os._exit(0)
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            os._exit(1)

    def monitor_loop(self):
        """Run monitor loop to scan ports and auto-connect devices."""
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
                        monolith = next((p for p in ports if p[0] in new_ports and any(s in (p[1] + str(p[2] if len(p) > 2 else '')).lower() for s in ['monolith', '2e8a:0002', '2e8a:0003', '1209:c550'])), None)
                        
                        if monolith:
                            logger.info(f"Tray Monitor: Found NEW device on {monolith[0]}, attempting auto-connect")
                            self.api.connect_serial(monolith[0])
                    
                    self.refresh()
                else:
                    if not self.api._serial_service.check_physical_connection_health():
                        logger.warning("Tray Monitor: Detected physical device disconnection")
                        self.refresh()
                        
                first_run = False
            except Exception as e:
                logger.error(f"Error in tray loop: {e}")
            time.sleep(2)
