import esptool
import logging
import threading
import sys
from io import StringIO
import time

logger = logging.getLogger(__name__)

class FlasherService:
    def __init__(self, on_progress_callback=None, on_finished_callback=None):
        self.on_progress = on_progress_callback
        self.on_finished = on_finished_callback
        self.is_flashing = False
        self._cancel_flag = False

    def flash(self, port, firmware_path, baud=460800):
        """
        Flash firmware to ESP32 using esptool.
        Blocking call (runs in its own thread usually).
        """
        if self.is_flashing:
            return False, "Already flashing"

        self.is_flashing = True
        self._cancel_flag = False
        
        try:
            logger.info(f"Starting flash on {port} with {firmware_path}")
            
            # Use esptool.main() but capture output to parse progress?
            # esptool is tricky to capture progress from because it prints to stdout directly.
            # We can run it as a subprocess or try to hook into it. 
            # Subprocess is safer for blocking/GIL reasons.
            
            import subprocess
            
            cmd = [
                sys.executable, "-m", "esptool",
                "--chip", "auto",
                "--port", port,
                "--baud", str(baud),
                "--before", "default_reset",
                "--after", "hard_reset",
                "write_flash", "-z",
                # ESP8266 usually flashes at 0x0000, ESP32 at 0x1000. 
                # "0x0000" is safer for auto. NodeMCU (ESP8266) needs 0x0000.
                "0x0000", firmware_path
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            output_log = []
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                output_log.append(line)
                logger.debug(f"ESPTOOL: {line}")
                
                if self.on_progress:
                     # Heuristic progress parsing
                     if "%" in line and "(" in line:
                         try:
                             parts = line.split("(")
                             last_part = parts[-1] 
                             if ")" in last_part:
                                 pct_str = last_part.split(")")[0].replace("%", "").strip()
                                 pct = int(pct_str)
                                 self.on_progress(f"Flashing: {pct}%", pct)
                         except:
                             pass
                     elif "Erasing" in line:
                         self.on_progress("Erasing flash...", 0)
                     elif "Compressed" in line:
                         self.on_progress("Writing...", 5)
                     elif "Connecting" in line:
                         self.on_progress("Connecting to device...", 2)

                if self._cancel_flag:
                    process.terminate()
                    self.is_flashing = False
                    return False, "Cancelled"

            process.wait()
            
            if process.returncode == 0:
                logger.info("Flash completed successfully")
                if self.on_finished:
                    self.on_finished(True, "Flash successful! Device restarting...")
                return True, "Success"
            else:
                # Use the last few lines of log as the error message
                last_lines = "; ".join(output_log[-3:]) if output_log else "Unknown error"
                err_msg = f"Esptool failed (code {process.returncode}): {last_lines}"
                logger.error(err_msg)
                if self.on_finished:
                    self.on_finished(False, err_msg)
                return False, err_msg

        except Exception as e:
            logger.error(f"Flash exception: {e}")
            if self.on_finished:
                self.on_finished(False, str(e))
            return False, str(e)
            
        finally:
            self.is_flashing = False
