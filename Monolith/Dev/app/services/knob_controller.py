import time
import threading
from pynput.keyboard import Controller, Key

class KnobController:
    def __init__(self, on_standard_execution=None):
        self.keyboard = Controller()
        self.mode = "Standard"
        self.speed = 1
        self.on_standard_execution = on_standard_execution
        
        # State for App Switcher (Alt+Tab)
        self.alt_held = False
        self.shift_held = False
        self.release_timer = None
        self.lock = threading.Lock()

    def set_mode(self, mode):
        self.mode = mode
        # Reset state when switching modes
        self.finalize_app_switch()

    def set_speed(self, speed):
        """Set knob rotation multiplier with bounds checking.
        
        Args:
            speed: Multiplier value (clamped to 1-10). Each physical tick 
                   triggers 'speed' logical actions.
        """
        try:
            self.speed = max(1, min(int(speed), 10))  # Clamp to [1, 10]
        except (ValueError, TypeError):
            self.speed = 1  # Safe default

    def handle_input(self, command):
        # Timeline Scrubber and Standard modes behave similarly - delegate to callback
        if self.mode in ["Standard", "Custom", "Timeline Scrubber"]:
            if self.on_standard_execution:
                for i in range(self.speed):
                    self.on_standard_execution(command)
                    # Add small delay between iterations for high speeds to prevent flooding
                    if i < self.speed - 1 and self.speed > 5:
                        time.sleep(0.015)  # 15ms delay for speeds > 5
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

            # Ensure Alt is held
            if not self.alt_held:
                self.keyboard.press(Key.alt)
                self.alt_held = True
            
            # Reset timer
            if self.release_timer:
                self.release_timer.cancel()
            
            self.release_timer = threading.Timer(0.35, self.finalize_app_switch)
            self.release_timer.start()

            if command == "KNOB_RIGHT":
                # Move forward: Alt + Tab
                if self.shift_held:
                    self.keyboard.release(Key.shift)
                    self.shift_held = False
                
                self.keyboard.press(Key.tab)
                self.keyboard.release(Key.tab)

            elif command == "KNOB_LEFT":
                # Move backward: Alt + Shift + Tab
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
        # Immediate switching, no holding required
        if command == "KNOB_RIGHT":
            # Alt + Esc
            with self.keyboard.pressed(Key.alt):
                self.keyboard.press(Key.esc)
                self.keyboard.release(Key.esc)
        
        elif command == "KNOB_LEFT":
            # Alt + Shift + Esc
            with self.keyboard.pressed(Key.alt):
                with self.keyboard.pressed(Key.shift):
                    self.keyboard.press(Key.esc)
                    self.keyboard.release(Key.esc)
        
        elif command == "KNOB_PRESS":
            # Maybe minimize? or Standard action? 
            # Let's fallback to standard for press in this mode if desired, 
            # but for now let's just ignore or map to something safe like Esc
            pass
