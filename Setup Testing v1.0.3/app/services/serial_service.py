import serial
import serial.tools.list_ports
import json
import threading
import time
import logging

logger = logging.getLogger(__name__)

class SerialListener(threading.Thread):
    def __init__(self, ser, lock, on_message, on_disconnect):
        super().__init__()
        self.ser = ser
        self.lock = lock
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            try:
                with self.lock:
                    if not self.ser or not self.ser.is_open:
                        break
                    # Non-blocking read with short timeout from Serial init
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line and self.on_message:
                    self.on_message(line)
            except serial.SerialException:
                self.running = False
                if self.on_disconnect:
                    self.on_disconnect()
            except Exception as e:
                logger.error(f"Error in serial listener: {e}")
                pass  # Prevent thread crash on other errors
            
            time.sleep(0.01) # Small sleep to prevent CPU hogging if readline returns immediately empty

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
        
        # Port cache to reduce expensive USB enumeration
        self._port_cache = None
        self._port_cache_time = 0
        self._port_cache_duration = 2.0  # Cache for 2 seconds

    @property
    def is_connected(self):
        with self.lock:
            return self.ser is not None and self.ser.is_open

    def check_physical_connection_health(self):
        """Verify if the current port still physically exists on the system."""
        if not self.port:
            return False
            
        try:
            available_ports = [p.device for p in serial.tools.list_ports.comports()]
            if self.port not in available_ports:
                logger.warning(f"Physical port {self.port} no longer available")
                # Trigger a cleaner disconnect if the port is gone but ser still thinks it's open
                self.disconnect()
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking physical connection health: {e}")
            return False

    def get_available_ports(self, use_cache=True):
        """Get available serial ports with optional caching."""
        current_time = time.time()
        
        # Return cached result if valid
        if use_cache and self._port_cache is not None:
            if current_time - self._port_cache_time < self._port_cache_duration:
                logger.debug("Returning cached port list")
                return self._port_cache
        
        # Fetch fresh port list
        try:
            ports = serial.tools.list_ports.comports()
            result = [(port.device, port.description) for port in ports]
            
            # Update cache
            self._port_cache = result
            self._port_cache_time = current_time
            logger.debug(f"Found {len(result)} serial ports")
            
            return result
        except Exception as e:
            logger.error(f"Error scanning serial ports: {e}")
            return []

    def connect(self, port, baudrate=115200):
        with self.lock:
            # Ensure previous connection is closed
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception as e:
                    logger.warning(f"Error closing serial port: {e}")
            
            try:
                # Timeout 0.1s for responsive disconnect
                # Disable DSR/DTR and RTS/CTS hardware flow control BEFORE opening
                # to prevent toggling GPIO0(D3) and RESET during connection
                self.ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=0.1,
                    dsrdtr=False,  # Disable DSR/DTR hardware flow control
                    rtscts=False   # Disable RTS/CTS hardware flow control
                )
                # Set DTR/RTS low for extra safety
                self.ser.dtr = False
                self.ser.rts = False
                
                self.port = port
                self.listener = SerialListener(
                    self.ser, 
                    self.lock, 
                    self.on_message_received, 
                    self.on_connection_lost
                )
                self.listener.start()
                return True
            except serial.SerialException:
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

    def on_message_received(self, message):
        if self.on_message_callback:
            self.on_message_callback(message)

    def on_connection_lost(self):
        if self.on_connection_lost_callback:
            self.on_connection_lost_callback()