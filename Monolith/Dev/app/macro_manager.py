import os
import sys
import subprocess
import time
import shlex
import logging
import ctypes
import threading
import json
from pathlib import Path
from pynput import keyboard
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
from pynput.mouse import Controller as MouseController, Button
import win32gui
import win32process
import win32con
import psutil

logger = logging.getLogger(__name__)

class WindowControlService:
    WM_SYSCOMMAND = 0x0112
    SC_MINIMIZE = 0xF020
    SC_MAXIMIZE = 0xF030
    SC_RESTORE = 0xF120
    
    def __init__(self):
        self._user32 = ctypes.windll.user32
        
    def minimize_windows(self):
        try:
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
        try:
            self._user32.keybd_event(0x10, 0, 0, 0) # Shift Down
            time.sleep(0.05)
            self._user32.keybd_event(0x5B, 0, 0, 0) # Win Down
            time.sleep(0.05)
            self._user32.keybd_event(0x4D, 0, 0, 0) # M Down
            time.sleep(0.05)
            self._user32.keybd_event(0x4D, 0, 0x0002, 0) # M Up
            time.sleep(0.05)
            self._user32.keybd_event(0x5B, 0, 0x0002, 0) # Win Up
            time.sleep(0.05)
            self._user32.keybd_event(0x10, 0, 0x0002, 0) # Shift Up
            logger.info("Sent Win+Shift+M to restore windows")
        except Exception as e:
            logger.error(f"Error restoring windows: {e}")

    def restore_active_window(self):
        try:
            hwnd = self._user32.GetForegroundWindow()
            if hwnd:
                self._user32.PostMessageW(hwnd, self.WM_SYSCOMMAND, self.SC_RESTORE, 0)
                logger.info(f"Sent restore command to window {hwnd}")
            else:
                logger.warning("No foreground window found to restore")
        except Exception as e:
            logger.error(f"Error restoring window: {e}")

class KnobController:
    def __init__(self, on_standard_execution=None):
        self.keyboard = KeyboardController()
        self.mode = "Standard"
        self.speed = 1
        self.on_standard_execution = on_standard_execution
        
        self.alt_held = False
        self.shift_held = False
        self.release_timer = None
        self.lock = threading.Lock()

    def set_mode(self, mode):
        self.mode = mode
        self.finalize_app_switch()

    def set_speed(self, speed):
        try:
            self.speed = max(1, min(int(speed), 10))
        except (ValueError, TypeError):
            self.speed = 1

    def handle_input(self, command):
        if self.mode in ["Standard", "Custom", "Timeline Scrubber"]:
            if self.on_standard_execution:
                for i in range(self.speed):
                    self.on_standard_execution(command)
                    if i < self.speed - 1 and self.speed > 5:
                        time.sleep(0.015)
            return

        if self.mode == "App Switcher (Alt+Tab)":
            self.handle_app_switcher(command)
        elif self.mode == "Window Switcher (Alt+Esc)":
            self.handle_window_switcher(command)

    def handle_app_switcher(self, command):
        with self.lock:
            if command == "KNOB_PRESS":
                self.finalize_app_switch()
                return

            if not self.alt_held:
                self.keyboard.press(Key.alt)
                self.alt_held = True
            
            if self.release_timer:
                self.release_timer.cancel()
            
            self.release_timer = threading.Timer(0.35, self.finalize_app_switch)
            self.release_timer.start()

            if command == "KNOB_RIGHT":
                if self.shift_held:
                    self.keyboard.release(Key.shift)
                    self.shift_held = False
                self.keyboard.press(Key.tab)
                self.keyboard.release(Key.tab)
            elif command == "KNOB_LEFT":
                if not self.shift_held:
                    self.keyboard.press(Key.shift)
                    self.shift_held = True
                self.keyboard.press(Key.tab)
                self.keyboard.release(Key.tab)

    def finalize_app_switch(self):
        with self.lock:
            if self.shift_held:
                self.keyboard.release(Key.shift)
                self.shift_held = False
            
            if self.alt_held:
                self.keyboard.release(Key.alt)
                self.alt_held = False
            
            if self.release_timer:
                self.release_timer.cancel()
                self.release_timer = None

    def handle_window_switcher(self, command):
        if command == "KNOB_RIGHT":
            with self.keyboard.pressed(Key.alt):
                self.keyboard.press(Key.esc)
                self.keyboard.release(Key.esc)
        elif command == "KNOB_LEFT":
            with self.keyboard.pressed(Key.alt):
                with self.keyboard.pressed(Key.shift):
                    self.keyboard.press(Key.esc)
                    self.keyboard.release(Key.esc)

class MacroExecutionService:
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

    def paste_text(self, text):
        import win32clipboard
        import win32con
        
        # Save current clipboard text
        old_text = None
        clipboard_opened = False
        try:
            win32clipboard.OpenClipboard()
            clipboard_opened = True
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                old_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                old_text = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
        except Exception as e:
            logger.warning(f"Failed to read original clipboard: {e}")
        finally:
            if clipboard_opened:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
        
        # Set new text to clipboard
        clipboard_opened = False
        try:
            win32clipboard.OpenClipboard()
            clipboard_opened = True
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        except Exception as e:
            logger.error(f"Failed to set clipboard: {e}")
            # Fallback to typing out if clipboard fails
            self.keyboard.type(text)
            return
        finally:
            if clipboard_opened:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
        
        # Trigger Ctrl+V
        try:
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('v')
            self.keyboard.release('v')
            self.keyboard.release(Key.ctrl)
        except Exception as e:
            logger.error(f"Failed to press paste hotkey: {e}")
            
        # Wait a small delay to let the active application process the paste event before we restore the clipboard
        time.sleep(0.08)
        
        # Restore original text
        if old_text is not None:
            clipboard_opened = False
            try:
                win32clipboard.OpenClipboard()
                clipboard_opened = True
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(old_text, win32clipboard.CF_UNICODETEXT)
            except Exception as e:
                logger.warning(f"Failed to restore clipboard: {e}")
            finally:
                if clipboard_opened:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        pass

    def execute_macro(self, macro, depth=0):
        if depth > 5:
            logger.warning("Max macro nesting depth reached, potential infinite loop")
            return
        if isinstance(macro, dict):
            macro_type = macro.get("type", "keys")
            
            if macro_type == "app" or macro_type == "launch":
                try:
                    path = macro.get("path", "")
                    if not path:
                        return
                    if path.startswith(("http://", "https://")):
                        from urllib.parse import urlparse
                        try:
                            result = urlparse(path)
                            if all([result.scheme, result.netloc]):
                                os.startfile(path)
                        except Exception:
                            logger.error(f"Failed to parse URL: {path}")
                    else:
                        path_obj = Path(path)
                        try:
                            abs_path = path_obj.resolve()
                            if abs_path.exists():
                                os.startfile(str(abs_path))
                        except Exception:
                            logger.error(f"Invalid path format: {path}")
                except Exception as e:
                    logger.error(f"Error launching application: {e}")
                return
            
            elif macro_type == "command":
                try:
                    command = macro.get("command", "")
                    if not command:
                        return
                    
                    if not self._is_command_safe(command):
                        return
                    
                    if command.lower().startswith("powershell"):
                        safe_cmd = command[10:].strip()
                        subprocess.Popen(["powershell", "-Command", safe_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                    elif command.lower().startswith("cmd"):
                        safe_cmd = command[3:].strip()
                        subprocess.Popen(["cmd", "/C", safe_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        try:
                            args = shlex.split(command, posix=False)
                            subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
                        except Exception as e:
                            logger.error(f"Command execution failed: {e}")
                except Exception as e:
                    logger.error(f"Error executing command: {e}")
                return
            
            elif macro_type == "text":
                text = macro.get("text", "")
                method = macro.get("method", "paste")
                if text:
                    if method == "paste":
                        self.paste_text(text)
                    else:
                        self.keyboard.type(text)
                return
            
            elif macro_type == "advanced":
                actions = macro.get("actions", [])
                self.execute_advanced_sequence(actions, depth=depth)
                return
            else:
                sequence = macro.get("sequence", [])
        else:
            sequence = macro

        self.execute_key_sequence(sequence)

    def execute_key_sequence(self, sequence):
        if isinstance(sequence, str):
            sequence = sequence.split(" + ")
            
        modifiers = []
        keys_to_press = []
        
        for item in sequence:
            key_lower = item.lower()
            if key_lower in ['ctrl', 'shift', 'alt', 'cmd', 'win', 'meta']:
                modifiers.append(self.get_key_object(item))
            else:
                keys_to_press.append(item)

        for mod in modifiers:
            self.keyboard.press(mod)

        for item in keys_to_press:
            key_obj = self.get_key_object(item)
            if isinstance(key_obj, str):
                if len(key_obj) == 1:
                    char_key = key_obj.lower()
                    self.keyboard.press(char_key)
                    self.keyboard.release(char_key)
                else:
                    self.keyboard.type(key_obj)
            else:
                self.keyboard.press(key_obj)
                self.keyboard.release(key_obj)
            time.sleep(0.01)

        for mod in reversed(modifiers):
            self.keyboard.release(mod)

    def execute_advanced_sequence(self, actions, depth=0):
        for action in actions:
            act_type = action.get("type")
            val = action.get("value")
            
            if act_type == "delay":
                time.sleep(float(val) / 1000.0)
            elif act_type == "text":
                self.keyboard.type(val)
            elif act_type == "key":
                self.execute_key_sequence([val])
            elif act_type == "mouse_click":
                button = Button.left if val == "left" else Button.right
                self.mouse.click(button, 1)
            elif act_type == "mouse_move":
                x, y = val
                self.mouse.position = (x, y)
            elif act_type == "key_down":
                key_obj = self.get_key_object(val)
                self.keyboard.press(key_obj)
            elif act_type == "key_up":
                key_obj = self.get_key_object(val)
                self.keyboard.release(key_obj)
            elif act_type == "macro":
                resolver = getattr(self, "macro_resolver", None)
                if resolver:
                    nested_macro = resolver(val)
                    if nested_macro:
                        self.execute_macro(nested_macro, depth=depth + 1)

    def get_key_object(self, key_str):
        key_map = {
            'ctrl': Key.ctrl, 'shift': Key.shift, 'alt': Key.alt,
            'win': Key.cmd, 'meta': Key.cmd, 'cmd': Key.cmd,
            'enter': Key.enter, 'esc': Key.esc, 'tab': Key.tab,
            'backspace': Key.backspace, 'delete': Key.delete, 'del': Key.delete,
            'space': Key.space, 'up': Key.up, 'down': Key.down,
            'left': Key.left, 'right': Key.right,
            'arrowup': Key.up, 'arrowdown': Key.down,
            'arrowleft': Key.left, 'arrowright': Key.right,
            'capslock': Key.caps_lock, 'numlock': Key.num_lock,
            'scrolllock': Key.scroll_lock, 'pause': Key.pause,
            'home': Key.home, 'end': Key.end,
            'pageup': Key.page_up, 'pagedown': Key.page_down,
            'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
            'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
            'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
            'volup': Key.media_volume_up, 'voldown': Key.media_volume_down,
            'volumemute': Key.media_volume_mute,
            'audiovolumemute': Key.media_volume_mute,
            'audiovolumedown': Key.media_volume_down,
            'audiovolumeup': Key.media_volume_up,
            'media_play_pause': Key.media_play_pause,
            'mediaplaypause': Key.media_play_pause,
            'media_next': Key.media_next, 'media_previous': Key.media_previous,
            'mediatracknext': Key.media_next, 'mediatrackprevious': Key.media_previous,
            'mediastop': Key.media_stop,
            'printscreen': Key.print_screen, 'insert': Key.insert,
            'browserhome': KeyCode.from_vk(172),
            'browsersearch': KeyCode.from_vk(170),
            'browserback': KeyCode.from_vk(166),
            'browserforward': KeyCode.from_vk(167),
            'browserstop': KeyCode.from_vk(169),
            'browserrefresh': KeyCode.from_vk(168),
            'browserfavorites': KeyCode.from_vk(171),
            'launchmail': KeyCode.from_vk(180),
            'launchmediaselect': KeyCode.from_vk(181),
            'launchapp1': KeyCode.from_vk(182),
            'launchapp2': KeyCode.from_vk(183)
        }
        return key_map.get(key_str.lower(), key_str)

    def _is_command_safe(self, command: str) -> bool:
        dangerous_keywords = [
            "downloadstring", "downloadfile", "invoke-expression", "iex",
            "invoke-webrequest", "iwr", "rmdir", "del ", "format ",
            "reg add", "net user", "net localgroup", "bitsadmin",
            "curl", "wget", "certutil", "ftp", "tftp", "http:", "https:",
            "cmd.exe", "powershell.exe", "bash", "sh"
        ]
        cmd_lower = command.lower()
        for kw in dangerous_keywords:
            if kw in cmd_lower:
                logger.error(f"SECURITY BLOCK: Blocked command due to dangerous keyword '{kw}'")
                return False
                
        # Block command chaining/pipe/redirection operators in shell commands
        # to prevent escaping command boundaries.
        if cmd_lower.startswith(("powershell", "cmd")):
            for char in [";", "&&", "||", "|", ">", "<"]:
                if char in command:
                    logger.error(f"SECURITY BLOCK: Blocked shell command due to chaining/redirection operator '{char}'")
                    return False
        return True

class MacroRecordingService:
    def __init__(self):
        self._listener = None
        self._window = None
        self._ui_bridge = None
        self._recording = False
        self._pressed_keys = set()
        
        self._esc_timer = None
        self._inactivity_timer = None
        self._inactivity_timeout = 300
        
    def set_ui_bridge(self, ui_bridge):
        self._ui_bridge = ui_bridge

    def start_recording(self):
        if self._recording:
            return
            
        logger.info("Starting macro recording with key suppression")
        self._recording = True
        self._pressed_keys.clear()
        
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
        
        if is_emergency and self._ui_bridge:
            self._ui_bridge.evaluate_js_safe("if(window.onRecordingEmergencyStop) window.onRecordingEmergencyStop()")

    def _emergency_stop(self):
        self.stop_recording(is_emergency=True)

    def _reset_inactivity_timer(self):
        if self._inactivity_timer:
            self._inactivity_timer.cancel()
        
        if self._recording:
            self._inactivity_timer = threading.Timer(self._inactivity_timeout, self._emergency_stop)
            self._inactivity_timer.daemon = True
            self._inactivity_timer.start()

    def _on_press(self, key):
        try:
            if key == keyboard.Key.esc:
                if self._esc_timer is None:
                    self._esc_timer = threading.Timer(1.5, self._emergency_stop)
                    self._esc_timer.daemon = True
                    self._esc_timer.start()
            
            self._reset_inactivity_timer()
            
            if key in self._pressed_keys:
                return
                
            self._pressed_keys.add(key)
            key_name = self._format_key(key)
            if self._ui_bridge:
                self._send_key_event('down', key_name)
        except Exception as e:
            logger.error(f"Error in on_press: {e}")

    def _on_release(self, key):
        try:
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
            safe_key = json.dumps(key_name)
            js = f"if(window.onRecordedKey) window.onRecordedKey('{event_type}', {safe_key})"
            self._ui_bridge.evaluate_js_safe(js)
        except Exception as e:
            logger.error(f"Error sending key event: {e}")

    def _format_key(self, key):
        if hasattr(key, 'char') and key.char:
            return key.char.upper()
            
        name = str(key).replace('Key.', '')
        mapping = {
            'ctrl_l': 'Ctrl', 'ctrl_r': 'Ctrl', 'alt_l': 'Alt', 'alt_r': 'Alt', 'alt_gr': 'Alt',
            'shift': 'Shift', 'shift_r': 'Shift', 'cmd': 'Win', 'cmd_l': 'Win', 'cmd_r': 'Win',
            'enter': 'Enter', 'esc': 'Esc', 'backspace': 'Backspace', 'delete': 'Del', 'space': 'Space',
            'tab': 'Tab', 'caps_lock': 'CapsLock', 'num_lock': 'NumLock', 'scroll_lock': 'ScrollLock', 'pause': 'Pause',
            'up': 'ArrowUp', 'down': 'ArrowDown', 'left': 'ArrowLeft', 'right': 'ArrowRight',
            'print_screen': 'PrintScreen', 'insert': 'Insert', 'home': 'Home', 'page_up': 'PageUp', 'page_down': 'PageDown', 'end': 'End',
            'media_volume_mute': 'AudioVolumeMute', 'media_volume_down': 'AudioVolumeDown', 'media_volume_up': 'AudioVolumeUp',
            'media_play_pause': 'MediaPlayPause', 'media_next': 'MediaTrackNext', 'media_previous': 'MediaTrackPrevious', 'media_stop': 'MediaStop',
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
        }
        if name in mapping:
            return mapping[name]
        return name.title()

class ProfileSwitcherService:
    def __init__(self, config: dict, on_profile_switch=None):
        self.enabled = config.get('auto_switching', {}).get('enabled', False)
        self.rules = config.get('auto_switching', {}).get('rules', {})
        self.on_profile_switch = on_profile_switch
        self.monitoring_thread = None
        self._stop_event = threading.Event()
        self.last_process = None
        self.check_interval = 1.0
        
        self.last_manual_profile = None
        self.current_auto_profile = None
        
        try:
            self.app_process_name = psutil.Process().name().lower()
        except Exception:
            self.app_process_name = "overcontrol.exe"
            
        logger.info(f"ProfileSwitcherService initialized. Enabled: {self.enabled}")

    def notify_manual_switch(self, profile_name: str):
        self.last_manual_profile = profile_name
        self.current_auto_profile = None
    
    def get_active_process_name(self) -> str:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name()
        except Exception:
            return None
    
    def should_switch_profile(self, process_name: str) -> str:
        if not process_name or not self.rules:
            return None
        if process_name in self.rules:
            return self.rules[process_name]
        for rule_process, profile_name in self.rules.items():
            if process_name.lower() == rule_process.lower():
                return profile_name
        return None
    
    def _monitor_loop(self):
        while not self._stop_event.is_set():
            try:
                if self.enabled:
                    current_process = self.get_active_process_name()
                    if current_process and current_process.lower() == self.app_process_name:
                        time.sleep(self.check_interval)
                        continue
                        
                    if current_process != self.last_process:
                        target_profile = self.should_switch_profile(current_process)
                        if target_profile:
                            if target_profile != self.current_auto_profile:
                                logger.info(f"Auto-switching: {current_process} -> {target_profile}")
                                self.current_auto_profile = target_profile
                                if self.on_profile_switch:
                                    self.on_profile_switch(target_profile)
                        elif self.current_auto_profile:
                            if self.last_manual_profile and self.last_manual_profile != self.current_auto_profile:
                                logger.info(f"Reverting to manual profile: {self.last_manual_profile}")
                                self.current_auto_profile = None 
                                if self.on_profile_switch:
                                    self.on_profile_switch(self.last_manual_profile)
                            else:
                                self.current_auto_profile = None
                        self.last_process = current_process
            except Exception as e:
                logger.error(f"Error in auto-switch loop: {e}")
            time.sleep(self.check_interval)
    
    def start(self):
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        self._stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()
    
    def stop(self):
        self._stop_event.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
    
    def set_enabled(self, enabled: bool):
        self.enabled = enabled
    
    def update_rules(self, rules: dict):
        self.rules = rules
        
    def update_config(self, config: dict):
        self.update_rules(config.get('auto_switching', {}).get('rules', {}))
        self.enabled = config.get('auto_switching', {}).get('enabled', self.enabled)
    
    def add_rule(self, process_name: str, profile_name: str):
        self.rules[process_name] = profile_name
    
    def remove_rule(self, process_name: str):
        if process_name in self.rules:
            del self.rules[process_name]

    def get_active_windows(self) -> list:
        process_names = set()
        def callback(hwnd, names_set):
            title = win32gui.GetWindowText(hwnd)
            if title:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid > 0:
                        proc = psutil.Process(pid)
                        name = proc.name()
                        if name:
                            names_set.add(name)
                except Exception:
                    pass
            return True
        try:
            win32gui.EnumWindows(callback, process_names)
        except Exception as e:
            logger.error(f"Error enumerating windows: {e}")
        return sorted(list(process_names))
