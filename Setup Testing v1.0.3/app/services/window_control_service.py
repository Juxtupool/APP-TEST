import ctypes
import logging
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

class WindowControlService:
    # Constants
    WM_SYSCOMMAND = 0x0112
    SC_MINIMIZE = 0xF020
    SC_MAXIMIZE = 0xF030
    SC_RESTORE = 0xF120
    
    def __init__(self):
        self._user32 = ctypes.windll.user32
        
    def minimize_windows(self):
        """Minimize all windows by simulating Win+M with delays."""
        try:
            # Simulate Win + M
            self._user32.keybd_event(0x5B, 0, 0, 0) # Win Down
            time.sleep(0.05)
            self._user32.keybd_event(0x4D, 0, 0, 0) # M Down
            time.sleep(0.05)
            
            self._user32.keybd_event(0x4D, 0, 0x0002, 0) # M Up
            time.sleep(0.05)
            self._user32.keybd_event(0x5B, 0, 0x0002, 0) # Win Up
            
            logger.info("Sent Win+M to minimize windows")
        except Exception as e:
            logger.error(f"Error minimizing windows: {e}")

    def restore_windows(self):
        """Restore all minimized windows (Undo Minimize All) by simulating Win+Shift+M with delays."""
        try:
            # Simulate Win + Shift + M
            # VK_LWIN = 0x5B, VK_SHIFT = 0x10, M = 0x4D
            # KEYEVENTF_KEYUP = 0x0002
            
            # Press Keys (Shift -> Win -> M)
            self._user32.keybd_event(0x10, 0, 0, 0) # Shift Down
            time.sleep(0.05)
            self._user32.keybd_event(0x5B, 0, 0, 0) # Win Down
            time.sleep(0.05)
            self._user32.keybd_event(0x4D, 0, 0, 0) # M Down
            time.sleep(0.05)
            
            # Release Keys (Reverse order)
            self._user32.keybd_event(0x4D, 0, 0x0002, 0) # M Up
            time.sleep(0.05)
            self._user32.keybd_event(0x5B, 0, 0x0002, 0) # Win Up
            time.sleep(0.05)
            self._user32.keybd_event(0x10, 0, 0x0002, 0) # Shift Up
            
            logger.info("Sent Win+Shift+M to restore windows")
        except Exception as e:
            logger.error(f"Error restoring windows: {e}")

    def restore_active_window(self):
        """Restore the currently active (foreground) window."""
        try:
            hwnd = self._user32.GetForegroundWindow()
            if hwnd:
                self._user32.PostMessageW(hwnd, self.WM_SYSCOMMAND, self.SC_RESTORE, 0)
                logger.info(f"Sent restore command to window {hwnd}")
            else:
                logger.warning("No foreground window found to restore")
        except Exception as e:
            logger.error(f"Error restoring window: {e}")
