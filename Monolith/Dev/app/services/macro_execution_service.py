import os
import time
import subprocess
import shlex
import logging
import ctypes 
from pathlib import Path
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
from pynput.mouse import Controller as MouseController, Button

logger = logging.getLogger(__name__)

class MacroExecutionService:
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

    def execute_macro(self, macro):
        """Execute macro with security validation."""
        if isinstance(macro, dict):
            macro_type = macro.get("type", "keys")
            
            if macro_type == "app" or macro_type == "launch":
                try:
                    path = macro.get("path", "")
                    if not path:
                        logger.error("No path specified for app/launch macro")
                        return
                    
                    # Validate path for security
                    if path.startswith(("http://", "https://")):
                        # URL - validate properly
                        from urllib.parse import urlparse
                        try:
                            result = urlparse(path)
                            if all([result.scheme, result.netloc]):
                                os.startfile(path)
                            else:
                                logger.error(f"Invalid URL: {path}")
                        except Exception:
                            logger.error(f"Failed to parse URL: {path}")
                    else:
                        # File or application - validate it exists
                        path_obj = Path(path)
                        # Resolve to absolute path to check existence securely
                        try:
                            abs_path = path_obj.resolve()
                            if abs_path.exists():
                                os.startfile(str(abs_path))
                            else:
                                logger.error(f"Path does not exist: {path}")
                        except Exception:
                            logger.error(f"Invalid path format: {path}")
                except (OSError, KeyError) as e:
                    logger.error(f"Error launching application: {e}")
                return
            
            elif macro_type == "command":
                try:
                    command = macro.get("command", "")
                    if not command:
                        logger.error("No command specified")
                        return
                    
                    # Sanitize: execution through list arguments is preferred over shell=True
                    
                    if command.lower().startswith("powershell"):
                        # Execute PowerShell safely by passing as argument list
                        # Encapsulate the command in quotes if not already? 
                        # Better: Use -Command and pass the rest.
                        safe_cmd = command[10:].strip() # remove 'powershell'
                        logger.info(f"Executing PowerShell command: {safe_cmd[:50]}...")
                        subprocess.Popen(["powershell", "-Command", safe_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                        
                    elif command.lower().startswith("cmd"):
                        # CMD is trickier without shell=True but we can use /C
                        safe_cmd = command[3:].strip() # remove 'cmd'
                        logger.info(f"Executing CMD command: {safe_cmd[:50]}...")
                        subprocess.Popen(["cmd", "/C", safe_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                        
                    else:
                        # For regular commands, use shlex to split safely
                        # This works for "calc", "notepad C:\foo.txt" etc.
                        try:
                            args = shlex.split(command, posix=False) # posix=False for Windows paths
                            subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
                        except (ValueError, FileNotFoundError, OSError) as e:
                            logger.error(f"Command execution failed: {e}")
                            # Do NOT fallback to shell=True
                            
                except Exception as e:
                    logger.error(f"Error executing command: {e}")
                return

            elif macro_type == "text":
                text = macro.get("text", "")
                if text:
                    self.keyboard.type(text)
                else:
                    logger.warning("Empty text macro")
                return

            elif macro_type == "advanced":
                actions = macro.get("actions", [])


                self.execute_advanced_sequence(actions)
                return



            else: # "keys" or legacy
                sequence = macro.get("sequence", [])
        else: # legacy
            sequence = macro

        self.execute_key_sequence(sequence)

    def execute_key_sequence(self, sequence):
        if isinstance(sequence, str):
            sequence = sequence.split(" + ")
            
        # Press modifiers first
        modifiers = []
        keys_to_press = []
        
        for item in sequence:
            key_lower = item.lower()
            if key_lower in ['ctrl', 'shift', 'alt', 'cmd', 'win', 'meta']:
                modifiers.append(self.get_key_object(item))
            else:
                keys_to_press.append(item)

        # Press modifiers
        for mod in modifiers:
            self.keyboard.press(mod)

        # Press other keys
        for item in keys_to_press:
            key_obj = self.get_key_object(item)
            if isinstance(key_obj, str):
                if len(key_obj) == 1:
                    # Fix for Win+D issue: 'D' comes in as uppercase from recorder.
                    # type('D') would simulate Shift+D.
                    # We treat single-char sequence items as hotkeys -> force lowercase press.
                    char_key = key_obj.lower()
                    self.keyboard.press(char_key)
                    self.keyboard.release(char_key)
                else:
                    self.keyboard.type(key_obj)
            else:
                self.keyboard.press(key_obj)
                self.keyboard.release(key_obj)
            time.sleep(0.01)

        # Release modifiers in reverse order
        for mod in reversed(modifiers):
            self.keyboard.release(mod)

    def execute_advanced_sequence(self, actions):
        for action in actions:
            act_type = action.get("type")
            val = action.get("value")
            
            if act_type == "delay":
                time.sleep(float(val) / 1000.0) # ms to s
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

    def get_key_object(self, key_str):
        key_map = {
            'ctrl': Key.ctrl, 'shift': Key.shift, 'alt': Key.alt,
            'win': Key.cmd, 'meta': Key.cmd, 'cmd': Key.cmd,
            'enter': Key.enter, 'esc': Key.esc, 'tab': Key.tab,
            'backspace': Key.backspace, 'delete': Key.delete,
            'space': Key.space, 'up': Key.up, 'down': Key.down,
            'left': Key.left, 'right': Key.right,
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
            # Keys missing from pynput keys on Windows, map via VK
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
        

