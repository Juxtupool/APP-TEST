import win32gui
import win32process
import psutil
import time
import threading
import logging
from typing import Dict, Optional, Callable

logger = logging.getLogger(__name__)


class ProfileSwitcherService:
    """
    Automatically switches profiles based on the active window/process.
    Runs in background thread and monitors foreground window changes.
    """
    
    def __init__(self, config: Dict, on_profile_switch: Optional[Callable] = None):
        """
        Args:
            config: Dictionary containing auto_switching rules
            on_profile_switch: Callback function(profile_name: str) when switching
        """
        self.enabled = config.get('auto_switching', {}).get('enabled', False)
        self.rules = config.get('auto_switching', {}).get('rules', {})
        self.on_profile_switch = on_profile_switch
        self.monitoring_thread = None
        self._stop_event = threading.Event()
        self.last_process = None
        self.check_interval = 1.0  # Check every second
        
        # Revert Logic State
        self.last_manual_profile = None
        self.current_auto_profile = None
        
        logger.info(f"ProfileSwitcherService initialized. Enabled: {self.enabled}, Rules: {len(self.rules)}")

    def notify_manual_switch(self, profile_name: str):
        """Update the last manually selected profile."""
        self.last_manual_profile = profile_name
        # If user manually switches, we break the auto-lock
        if self.current_auto_profile:
             logger.info("Manual switch broke auto-profile lock")
        self.current_auto_profile = None
    
    def get_active_process_name(self) -> Optional[str]:
        """Get the process name of the currently active window."""
        try:
            # Get foreground window handle
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None
            
            # Get process ID from window
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get process name
            process = psutil.Process(pid)
            return process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
            logger.debug(f"Could not get active process: {e}")
            return None
    
    def should_switch_profile(self, process_name: str) -> Optional[str]:
        """
        Check if we should switch profile for this process.
        Returns profile name if match found, None otherwise.
        """
        if not process_name or not self.rules:
            return None
        
        # Exact match first
        if process_name in self.rules:
            return self.rules[process_name]
        
        # Case-insensitive match
        for rule_process, profile_name in self.rules.items():
            if process_name.lower() == rule_process.lower():
                return profile_name
        
        return None
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.info("Profile auto-switching monitor started")
        
        while not self._stop_event.is_set():
            try:
                if self.enabled:
                    current_process = self.get_active_process_name()
                    
                    if current_process != self.last_process:
                        target_profile = self.should_switch_profile(current_process)
                        
                        if target_profile:
                            # Found a matching rule
                            if target_profile != self.current_auto_profile:
                                logger.info(f"Auto-switching: {current_process} -> {target_profile}")
                                self.current_auto_profile = target_profile
                                if self.on_profile_switch:
                                    self.on_profile_switch(target_profile)
                        
                        elif self.current_auto_profile:
                            # No rule, but we are in an auto-profile. Revert!
                            if self.last_manual_profile and self.last_manual_profile != self.current_auto_profile:
                                logger.info(f"Reverting to manual profile: {self.last_manual_profile}")
                                self.current_auto_profile = None 
                                if self.on_profile_switch:
                                    self.on_profile_switch(self.last_manual_profile)
                            else:
                                # Fallback or already there
                                self.current_auto_profile = None
                        
                        self.last_process = current_process
                
            except Exception as e:
                logger.error(f"Error in profile switcher monitor loop: {e}")
            
            # Wait before next check
            time.sleep(self.check_interval)
        
        logger.info("Profile auto-switching monitor stopped")
    
    def start(self):
        """Start the background monitoring thread."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.warning("Monitor thread already running")
            return
        
        self._stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Profile switcher started")
    
    def stop(self):
        """Stop the background monitoring thread."""
        self._stop_event.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
        logger.info("Profile switcher stopped")
    
    def set_enabled(self, enabled: bool):
        """Enable or disable auto-switching."""
        self.enabled = enabled
        logger.info(f"Profile auto-switching {'enabled' if enabled else 'disabled'}")
    
    def update_rules(self, rules: Dict[str, str]):
        """Update the switching rules."""
        self.rules = rules
        logger.info(f"Updated auto-switching rules: {len(rules)} rules")
        
    def update_config(self, config: Dict):
        """Update configuration (compatibility wrapper)."""
        rules = config.get('auto_switching', {}).get('rules', {})
        self.update_rules(rules)
        self.enabled = config.get('auto_switching', {}).get('enabled', self.enabled)
    
    def add_rule(self, process_name: str, profile_name: str):
        """Add a single rule."""
        self.rules[process_name] = profile_name
        logger.info(f"Added rule: {process_name} -> {profile_name}")
    
    def remove_rule(self, process_name: str):
        """Remove a rule."""
        if process_name in self.rules:
            del self.rules[process_name]
            logger.info(f"Removed rule: {process_name}")

    def get_active_windows(self) -> list:
        """Returns a list of unique process names from currently running windows."""
        process_names = set()
        
        def callback(hwnd, names_set):
            # We want to include minimized windows too, so we're more lenient than just IsWindowVisible
            # But we still want actual application windows (with titles)
            title = win32gui.GetWindowText(hwnd)
            if title:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid > 0:
                        proc = psutil.Process(pid)
                        name = proc.name()
                        if name:
                            names_set.add(name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return True
        
        try:
            win32gui.EnumWindows(callback, process_names)
        except Exception as e:
            logger.error(f"Error enumerating windows: {e}")
            
        return sorted(list(process_names))
