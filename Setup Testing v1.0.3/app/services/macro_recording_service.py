import logging
import json
import threading
from pynput import keyboard

logger = logging.getLogger(__name__)

class MacroRecordingService:
    def __init__(self):
        self._listener = None
        self._window = None
        self._ui_bridge = None
        self._recording = False
        self._pressed_keys = set()
        
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

    def stop_recording(self):
        if not self._recording:
            return
            
        logger.info("Stopping macro recording")
        self._recording = False
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.error(f"Error stopping listener: {e}")
            self._listener = None
        self._pressed_keys.clear()

    def _on_press(self, key):
        try:
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
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)
                
            key_name = self._format_key(key)
            if self._ui_bridge:
                self._send_key_event('up', key_name)
        except Exception as e:
            logger.error(f"Error in on_release: {e}")

    def _send_key_event(self, event_type, key_name):
        try:
            # We need to act quickly, so we fire and forget via the bridge
            # The bridge 'evaluate_js' is usually thread-safe or schedules on main thread
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
        
        # Mapping to match frontend expectations (app.js handleRecordingKey)
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
            'media_volume_mute': 'AudioVolumeMute',
            'media_volume_down': 'AudioVolumeDown',
            'media_volume_up': 'AudioVolumeUp',
            'media_play_pause': 'MediaPlayPause', 
            'media_next': 'MediaTrackNext',
            'media_previous': 'MediaTrackPrevious',
            'media_stop': 'MediaStop'
        }
        
        if name in mapping:
            return mapping[name]
            
        # Title case for F-keys and others (f1 -> F1)
        return name.title()
