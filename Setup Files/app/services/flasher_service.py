import sys
import subprocess
import threading
import re
import time
import os
import logging

logger = logging.getLogger(__name__)

class FlasherService:
    def __init__(self, on_progress_callback=None, on_finished_callback=None):
        """
        :param on_progress_callback: func(message: str, percent: int)
        :param on_finished_callback: func(success: bool, message: str)
        """
        self.on_progress_callback = on_progress_callback
        self.on_finished_callback = on_finished_callback
        self._process = None
        self._thread = None
        self._stop_event = threading.Event()
        
    def flash(self, port, file_path):
        """
        Start the flashing process in a separate thread.
        """
        if self._thread and self._thread.is_alive():
            return False, "Flashing already in progress"

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_esptool, args=(port, file_path))
        self._thread.daemon = True
        self._thread.start()
        return True, "Flashing started"

    def cancel(self):
        """
        Attempt to cancel the running process.
        """
        self._stop_event.set()
        if self._process:
            self._process.terminate()
            
    def _run_esptool(self, port, file_path):
        try:
            # Construct command
            cmd = [
                sys.executable, "-m", "esptool",
                "--port", port,
                "--baud", "460800",
                "write_flash",
                "--flash_size=detect",
                "0", file_path
            ]
            
            # 1. Notify Start
            self._emit_progress(f"Starting esptool on {port}...", 0)
            self._emit_progress(f"File: {os.path.basename(file_path)}", 0)

            # 2. Start Process
            # Use distinct creation flags for Windows to hide the console window if possible
            kwargs = {}
            if sys.platform == "win32":
                 kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                text=True,  # Text mode for easier string handling
                bufsize=1,  # Line buffered
                universal_newlines=True,
                **kwargs
            )

            # 3. Notify that flashing has started
            self._emit_progress("Starting flash...", 0)
            
            # 4. Wait for process to complete
            while True:
                if self._stop_event.is_set():
                    self._process.terminate()
                    self._emit_finished(False, "Cancelled by user")
                    return

                # Check if process has finished
                if self._process.poll() is not None:
                    break
                    
                time.sleep(0.1)  # Check every 100ms

            # 5. Check Exit Code
            rc = self._process.poll()
            if rc == 0:
                self._emit_progress("Flashing Complete", 100)
                self._emit_finished(True, "Firmware updated successfully!")
            else:
                self._emit_finished(False, f"Process failed with exit code {rc}")

        except Exception as e:
            self._emit_finished(False, f"Exception: {str(e)}")
        finally:
            self._process = None

    def _emit_progress(self, message, percent):
        """Emit progress update with error handling."""
        if self.on_progress_callback:
            try:
                self.on_progress_callback(message, percent)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def _emit_finished(self, success, message):
        """Emit completion status with error handling."""
        if self.on_finished_callback:
            try:
                self.on_finished_callback(success, message)
            except Exception as e:
                logger.error(f"Error in finished callback: {e}")
