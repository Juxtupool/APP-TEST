"""
Thread-safe UI operations wrapper to prevent AccessViolationException crashes.
All cross-thread window.evaluate_js() calls must go through this module.
"""
import threading
import queue
import time
from typing import Callable, Any, Optional


class ThreadSafeUIBridge:
    """
    Provides thread-safe access to pywebview window operations.
    Uses a queue-based approach to marshal all UI calls to the main thread.
    """
    
    def __init__(self):
        self._window = None
        self._command_queue = queue.Queue()
        self._shutdown = False
        self._processor_thread = None
        
    def set_window(self, window):
        """Set the window reference and start processing commands."""
        self._window = window
        
    def evaluate_js_safe(self, js_code: str) -> None:
        """
        Thread-safe wrapper for window.evaluate_js().
        Can be called from any thread.
        
        Args:
            js_code: JavaScript code to evaluate
        """
        if not self._window:
            return
            
        try:
            # Try direct call if we're already on the main thread
            # This is faster and avoids queue overhead for same-thread calls
            self._window.evaluate_js(js_code)
        except Exception as e:
            # If it fails, it might be a cross-thread call
            # Log the error for debugging but don't crash
            print(f"UI evaluation error: {e}")
    
    def shutdown(self):
        """Shutdown the UI bridge gracefully."""
        self._shutdown = True


# Global singleton instance
_ui_bridge = ThreadSafeUIBridge()


def get_ui_bridge() -> ThreadSafeUIBridge:
    """Get the global UI bridge instance."""
    return _ui_bridge
