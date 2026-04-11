import logging
import json
import threading
import time
from pynput import keyboard

logger = logging.getLogger(__name__)

class MacroRecordingService:
    def __init__(self):
        self._listener = None
        self._window = None
        self._ui_bridge = None
        self._recording = False
        self._pressed_keys = set()
        
        # Safety timers
        self._esc_timer = None
        self._inactivity_timer = None
        self._inactivity_timeout = 300 # 5 minutes
        
    def set_ui_bridge(self, ui_bridge):
        self._ui_bridge = ui_bridge

    def start_recording(self):
        if self._recording:
            return
            
        logger.info("Starting macro recording with key suppression")
        self._recording = True
        self._pressed_keys.clear()
        
        # Start global listener with suppress=True to block keys from OS
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=True
        )
        self._listener.start()
        
        self._reset_inactivity_timer()

    def stop_recording(self, is_emergency=False):
        if not self._recording:
            return
            
        logger.info(f"Stopping macro recording{' (EMERGENCY)' if is_emergency else ''}")
        self._recording = False
        
        # Clean up timers
        if self._esc_timer:
            self._esc_timer.cancel()
            self._esc_timer = None
        if self._inactivity_timer:
            self._inactivity_timer.cancel()
            self._inactivity_timer = None
            
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.error(f"Error stopping listener: {e}")
            self._listener = None
        self._pressed_keys.clear()
        
        # Notify frontend if it was an emergency stop
        if is_emergency and self._ui_bridge:
            self._ui_bridge.evaluate_js_safe("if(window.onRecordingEmergencyStop) window.onRecordingEmergencyStop()")

    def _emergency_stop(self):
        """Called when safety conditions (Esc hold or timeout) are met."""
        logger.warning("Emergency stop triggered. Releasing keyboard hooks.")
        self.stop_recording(is_emergency=True)

    def _reset_inactivity_timer(self):
        """Resets the safety timeout that prevents permanent keyboard lockup if user forgets."""
        if self._inactivity_timer:
            self._inactivity_timer.cancel()
        
        if self._recording:
            self._inactivity_timer = threading.Timer(self._inactivity_timeout, self._emergency_stop)
            self._inactivity_timer.daemon = True
            self._inactivity_timer.start()

    def _on_press(self, key):
        try:
            # Panic Key: Hold Escape for 1.5s to force release keyboard
            if key == keyboard.Key.esc:
                if self._esc_timer is None:
                    self._esc_timer = threading.Timer(1.5, self._emergency_stop)
                    self._esc_timer.daemon = True
                    self._esc_timer.start()
            
            # Reset inactivity timer on any activity
            self._reset_inactivity_timer()
            
            # Ignore auto-repeat key events
            if key in self._pressed_keys:
                return
                
            self._pressed_keys.add(key)
            
            key_name = self._format_key(key)
            # Send to frontend
            if self._ui_bridge:
                self._send_key_event('down', key_name)
        except Exception as e:
            logger.error(f"Error in on_press: {e}")

    def _on_release(self, key):
        try:
            # Cancel panic timer if Esc is released early
            if key == keyboard.Key.esc:
                if self._esc_timer:
                    self._esc_timer.cancel()
                    self._esc_timer = None
            
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)
                
            key_name = self._format_key(key)
            if self._ui_bridge:
                self._send_key_event('up', key_name)
        except Exception as e:
            logger.error(f"Error in on_release: {e}")

    def _send_key_event(self, event_type, key_name):
        try:
            # Use fixed JSON encoding for safety
            safe_key = json.dumps(key_name)
            js = f"if(window.onRecordedKey) window.onRecordedKey('{event_type}', {safe_key})"
            self._ui_bridge.evaluate_js_safe(js)
        except Exception as e:
            logger.error(f"Error sending key event: {e}")

    def _format_key(self, key):
        """Map pynput key to frontend expected string format"""
        if hasattr(key, 'char') and key.char:
            return key.char.upper() # Standard keys return char
            
        # Special keys
        name = str(key).replace('Key.', '')
        
        # Mapping to match frontend expectations
        mapping = {
            'ctrl_l': 'Ctrl',
            'ctrl_r': 'Ctrl', 
            'alt_l': 'Alt',
            'alt_r': 'Alt',
            'alt_gr': 'Alt',
            'shift': 'Shift',
            'shift_r': 'Shift',
            'cmd': 'Win',
            'cmd_l': 'Win',
            'cmd_r': 'Win',
            'enter': 'Enter',
            'esc': 'Esc',
            'backspace': 'Backspace',
            'delete': 'Del',
            'space': 'Space',
            'tab': 'Tab',
            'caps_lock': 'CapsLock',
            'num_lock': 'NumLock',
            'scroll_lock': 'ScrollLock',
            'pause': 'Pause',
            'up': 'ArrowUp',
            'down': 'ArrowDown',
            'left': 'ArrowLeft',
            'right': 'ArrowRight',
            'print_screen': 'PrintScreen',
            'insert': 'Insert',
            'home': 'Home', 
            'page_up': 'PageUp',
            'page_down': 'PageDown',
            'end': 'End',
            # Media
            'media_volume_mute': 'AudioVolumeMute',
            'media_volume_down': 'AudioVolumeDown',
            'media_volume_up': 'AudioVolumeUp',
            'media_play_pause': 'MediaPlayPause', 
            'media_next': 'MediaTrackNext',
            'media_previous': 'MediaTrackPrevious',
            'media_stop': 'MediaStop',
            # Numpad variants
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', 
            '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
        }
        
        if name in mapping:
            return mapping[name]
        
        # Handle Numpad keys (often str(key) is '<96>', '<97>' etc on some windows setups)
        # but pynput usually exposes them as keyboard.Key.insert etc if NumLock is off
        # If NumLock is on, they might be keyboard.KeyCode(vk=96)
        
        # Title case for F-keys and others (f1 -> F1)
        return name.title()
