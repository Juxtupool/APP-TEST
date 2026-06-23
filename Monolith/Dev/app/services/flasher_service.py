import logging
import threading
import sys
import time
import os
import shutil
import serial
import win32api

logger = logging.getLogger(__name__)

class FlasherService:
    def __init__(self, on_progress_callback=None, on_finished_callback=None):
        self.on_progress = on_progress_callback
        self.on_finished = on_finished_callback
        self.is_flashing = False
        self._cancel_flag = False

    def flash(self, port, firmware_path, baud=115200):
        """
        Flash firmware to RP2040 using USB Mass Storage UF2 bootloading.
        """
        if self.is_flashing:
            return False, "Already flashing"

        self.is_flashing = True
        self._cancel_flag = False
        
        try:
            logger.info(f"Starting RP2040 flash process on {port} with {firmware_path}")
            
            if self.on_progress:
                self.on_progress("Resetting device into bootloader mode...", 10)

            # 1. Reset RP2040 into BOOTSEL mode via 1200 baud trick
            try:
                ser = serial.Serial(port, 1200)
                ser.close()
                logger.info("Sent 1200 baud reset to bootloader")
            except Exception as e:
                logger.warning(f"Could not perform 1200 baud reset on {port}: {e}. Device might already be in BOOTSEL mode.")

            if self.on_progress:
                self.on_progress("Waiting for RPI-RP2 USB drive...", 30)

            # 2. Polling for RPI-RP2 volume to mount
            drive = None
            for _ in range(30):
                if self._cancel_flag:
                    self.is_flashing = False
                    return False, "Cancelled"

                try:
                    drives_str = win32api.GetLogicalDriveStrings()
                    drives = [d for d in drives_str.split('\x00') if d]
                    for d in drives:
                        try:
                            vol_name = win32api.GetVolumeInformation(d)[0]
                            if vol_name == "RPI-RP2":
                                drive = d
                                break
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Error checking drives: {e}")

                if drive:
                    break
                time.sleep(0.5)

            if not drive:
                err_msg = "RP2040 Bootloader drive (RPI-RP2) not found. Please verify connection or press BOOTSEL button."
                logger.error(err_msg)
                if self.on_finished:
                    self.on_finished(False, err_msg)
                return False, err_msg

            if self.on_progress:
                self.on_progress("Copying firmware to device...", 70)

            # 3. Copy the UF2 firmware file to the mounted drive
            if self._cancel_flag:
                self.is_flashing = False
                return False, "Cancelled"

            try:
                shutil.copy(firmware_path, drive)
                logger.info(f"Successfully copied {firmware_path} to {drive}")
                
                # Attempt to close the Explorer window that Windows automatically pops up
                def close_windows_delayed():
                    for _ in range(6):
                        time.sleep(0.3)
                        self._close_rpi_explorer_window()
                threading.Thread(target=close_windows_delayed, daemon=True).start()
                
            except Exception as e:
                err_msg = f"Failed to copy firmware file: {e}"
                logger.error(err_msg)
                if self.on_finished:
                    self.on_finished(False, err_msg)
                return False, err_msg

            if self.on_progress:
                self.on_progress("Flash completed successfully!", 100)

            if self.on_finished:
                self.on_finished(True, "Flash successful! Device restarting...")
            return True, "Success"

        except Exception as e:
            logger.error(f"Flash exception: {e}")
            if self.on_finished:
                self.on_finished(False, str(e))
            return False, str(e)
            
        finally:
            self.is_flashing = False

    def _close_rpi_explorer_window(self):
        import win32gui
        import win32con
        
        def callback(hwnd, extra):
            if win32gui.GetClassName(hwnd) == "CabinetWClass":
                title = win32gui.GetWindowText(hwnd)
                if "RPI-RP2" in title:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    logger.info(f"Closed RPI-RP2 explorer window: '{title}'")
        
        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug(f"Failed to enumerate windows: {e}")
