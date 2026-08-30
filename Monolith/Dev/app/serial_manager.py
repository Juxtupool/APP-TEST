import os
import sys
import time
import json
import shutil
import logging
import threading
import serial
import serial.tools.list_ports
import win32api
import win32gui
import win32con

logger = logging.getLogger(__name__)

class SerialListener(threading.Thread):
    def __init__(self, ser, on_message, on_disconnect):
        super().__init__()
        self.ser = ser
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            try:
                ser = self.ser
                if not ser or not ser.is_open:
                    break
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line and self.on_message:
                    self.on_message(line)
            except (serial.SerialException, OSError, Exception) as e:
                logger.warning(f"Error in serial listener: {e}")
                self.running = False
                if self.on_disconnect:
                    self.on_disconnect()
                break
            
            time.sleep(0.005)

    def stop(self):
        self.running = False

class SerialService:
    def __init__(self):
        self.ser = None
        self.listener = None
        self.port = None
        self.lock = threading.Lock()
        self.on_message_callback = None
        self.on_connection_lost_callback = None
        
        self._port_cache = None
        self._port_cache_time = 0
        self._port_cache_duration = 0.5
        self._last_connected_port = None

    @property
    def is_connected(self):
        with self.lock:
            return self.ser is not None and self.ser.is_open

    def check_physical_connection_health(self):
        with self.lock:
            if not self.port or not self.ser or not self.ser.is_open:
                return False
            ser = self.ser
            port = self.port
            
        try:
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            if port not in available_ports:
                logger.warning(f"Physical port {port} no longer available")
                self.on_connection_lost()
                return False
            
            # Verify the OS serial handle is active (catches handle death post PC sleep/wake)
            _ = ser.in_waiting
            return True
        except Exception as e:
            logger.warning(f"Serial handle health check failed (post PC sleep/wake): {e}")
            self.on_connection_lost()
            return False

    def get_available_ports(self, use_cache=True):
        current_time = time.time()
        
        if use_cache and self._port_cache is not None:
            if current_time - self._port_cache_time < self._port_cache_duration:
                return self._port_cache
        
        try:
            ports = serial.tools.list_ports.comports()
            filtered_ports = []
            for port in ports:
                hwid = port.hwid.upper() if getattr(port, 'hwid', None) else ""
                desc = port.description.lower() if getattr(port, 'description', None) else ""
                
                if 'BTHENUM' in hwid or 'bluetooth' in desc:
                    continue
                
                is_monolith = 'monolith' in desc.lower() or 'monolith' in hwid.lower()
                is_rp2040 = '2E8A:0002' in hwid or '2E8A:0003' in hwid or '239A:CAFE' in hwid or '239A:' in hwid
                is_ch552 = '1209:C550' in hwid
                
                if is_monolith or is_rp2040 or is_ch552:
                    filtered_ports.insert(0, (port.device, port.description, port.hwid))
                else:
                    filtered_ports.append((port.device, port.description, port.hwid))
                
            self._port_cache = filtered_ports
            self._port_cache_time = current_time
            return filtered_ports
        except Exception as e:
            logger.error(f"Error scanning serial ports: {e}")
            return []

    def connect(self, port, baudrate=115200):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception as e:
                    logger.warning(f"Error closing serial port: {e}")
            
            try:
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=0.1,
                    dsrdtr=False,
                    rtscts=False
                )
                self.ser.dtr = True
                self.ser.rts = True
                
                self.port = port
                self._last_connected_port = port
                self.listener = SerialListener(
                    self.ser, 
                    self.on_message_received, 
                    self.on_connection_lost
                )
                self.listener.start()
                
                def request_version():
                    time.sleep(1.0)
                    if self.ser and self.ser.is_open:
                        self.send_raw_command("GET_VERSION")
                
                threading.Thread(target=request_version, daemon=True).start()
                return True
            except Exception as e:
                logger.error(f"Failed to connect to {port}: {e}")
                self.ser = None
                self.port = None
                return False

    def disconnect(self):
        if self.listener:
            self.listener.stop()
            self.listener.join(timeout=0.2)
            self.listener = None
        
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                    logger.info("Serial port closed")
                except Exception as e:
                    logger.warning(f"Error closing serial port: {e}")
            self.ser = None
            self.port = None

    def send_data(self, data):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    json_data = json.dumps(data)
                    self.ser.write(json_data.encode('utf-8') + b'\n')
                    return True
                except (serial.SerialException, TypeError) as e:
                    logger.error(f"Error sending serial data: {e}")
                    return False
            return False

    def send_raw_command(self, cmd_str):
        with self.lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(cmd_str.encode('utf-8') + b'\n')
                    return True
                except serial.SerialException as e:
                    logger.error(f"Error sending raw command: {e}")
                    return False
            return False

    def on_message_received(self, message):
        if self.on_message_callback:
            self.on_message_callback(message)

    def on_connection_lost(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

        last_port = self.port or self._last_connected_port
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None
            self.port = None

        if last_port:
            self._last_connected_port = last_port
        if self.on_connection_lost_callback:
            self.on_connection_lost_callback()

class FlasherService:
    def __init__(self, on_progress_callback=None, on_finished_callback=None):
        self.on_progress = on_progress_callback
        self.on_finished = on_finished_callback
        self.is_flashing = False
        self._cancel_flag = False

    def flash(self, port, firmware_path, baud=115200):
        if self.is_flashing:
            return False, "Already flashing"

        self.is_flashing = True
        self._cancel_flag = False
        
        try:
            logger.info(f"Starting RP2040 flash process on {port} with {firmware_path}")
            if self.on_progress:
                self.on_progress("Resetting device into bootloader mode...", 10)

            try:
                ser = serial.Serial(port, 1200)
                ser.close()
                logger.info("Sent 1200 baud reset to bootloader")
            except Exception as e:
                logger.warning(f"Could not reset on {port}: {e}. Device might already be in BOOTSEL.")

            if self.on_progress:
                self.on_progress("Waiting for RPI-RP2 USB drive...", 30)

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
                err_msg = "RP2040 Bootloader drive (RPI-RP2) not found. Verify connection or press BOOTSEL."
                logger.error(err_msg)
                if self.on_finished:
                    self.on_finished(False, err_msg)
                return False, err_msg

            if self.on_progress:
                self.on_progress("Copying firmware to device...", 70)

            if self._cancel_flag:
                self.is_flashing = False
                return False, "Cancelled"

            try:
                shutil.copy(firmware_path, drive)
                logger.info(f"Successfully copied {firmware_path} to {drive}")
                
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
