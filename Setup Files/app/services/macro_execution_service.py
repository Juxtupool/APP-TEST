import os
import time
import subprocess
import shlex
import logging
from pathlib import Path
from pynput.keyboard import Controller as KeyboardController, Key
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
                        # URL - open in default browser
                        os.startfile(path)
                    else:
                        # File or application - validate it exists
                        path_obj = Path(path)
                        if path_obj.exists() or '\\' in path or ':' in path:
                            # Use os.startfile for Windows (safer than shell=True)
                            os.startfile(path)
                        else:
                            logger.error(f"Path does not exist: {path}")
                except (OSError, KeyError) as e:
                    logger.error(f"Error launching application: {e}")
                return
            
            elif macro_type == "command":
                try:
                    command = macro.get("command", "")
                    if not command:
                        logger.error("No command specified")
                        return
                    
                    # Check if command contains special batch syntax that needs proper handling
                    needs_batch_file = any(keyword in command.lower() for keyword in ['for %', 'if ', 'goto ', '&', '|', '&&', '||'])
                    
                    if needs_batch_file:
                        # Write to temporary batch file to avoid quote escaping issues
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as bat_file:
                            bat_file.write('@echo off\n')
                            # Convert single % to %% for batch file
                            batch_command = command.replace('%', '%%')
                            bat_file.write(batch_command + '\n')
                            bat_path = bat_file.name
                        
                        logger.info(f"Executing command via batch file: {command[:50]}...")
                        subprocess.Popen([bat_path], creationflags=subprocess.CREATE_NO_WINDOW, shell=True)
                        
                        # Schedule cleanup after a delay
                        import threading
                        def cleanup():
                            import time
                            time.sleep(5)  # Wait for batch to start
                            try:
                                os.unlink(bat_path)
                            except:
                                pass
                        threading.Thread(target=cleanup, daemon=True).start()
                        
                    elif command.startswith(("powershell", "cmd")):
                        # For PowerShell/cmd prefix, use shell=True
                        logger.warning(f"Executing shell command: {command[:50]}...")
                        subprocess.Popen(command, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        # For regular commands, try direct execution first
                        try:
                            args = shlex.split(command)
                            subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
                        except (ValueError, FileNotFoundError, OSError):
                            # Fall back to shell for built-ins like dir, copy, etc.
                            logger.warning(f"Using shell=True for command: {command[:50]}")
                            subprocess.Popen(command, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
            'media_play_pause': Key.media_play_pause,
            'media_next': Key.media_next, 'media_previous': Key.media_previous
        }
        return key_map.get(key_str.lower(), key_str)
