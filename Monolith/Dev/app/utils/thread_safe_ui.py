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
        self._lock = threading.Lock()
        
    def set_window(self, window):
        """Set the window reference and start processing commands."""
        with self._lock:
            self._window = window
            if self._processor_thread is None or not self._processor_thread.is_alive():
                self._shutdown = False
                self._processor_thread = threading.Thread(
                    target=self._process_queue, 
                    name="UIBridgeProcessor",
                    daemon=True
                )
                self._processor_thread.start()
        
    def _process_queue(self):
        """Worker thread that processes JS evaluation requests sequentially."""
        while not self._shutdown:
            try:
                # Use a timeout so we can check the shutdown flag periodically
                js_code = self._command_queue.get(timeout=0.5)
                
                if self._window:
                    try:
                        # pywebview's evaluate_js is thread-safe in principle (marshals to main),
                        # but sequential processing in a dedicated thread prevents race conditions
                        # and resource contention that leads to AccessViolation crashes.
                        self._window.evaluate_js(js_code)
                    except Exception as e:
                        # Log error but keep the processor thread alive
                        print(f"UI evaluation error in worker: {e}")
                
                self._command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Catch-all to ensure the thread doesn't die unexpectedly
                print(f"Critical error in UI processor thread: {e}")
                time.sleep(1) # Prevent tight loop on recurring errors
    
    def evaluate_js_safe(self, js_code: str) -> None:
        """
        Thread-safe wrapper for window.evaluate_js().
        Can be called from any thread.
        
        Args:
            js_code: JavaScript code to evaluate
        """
        # Always queue the code, even if window isn't set yet (will process once set_window is called)
        self._command_queue.put(js_code)
        
        # Self-healing: if thread died for some reason, restart it
        if self._window and (self._processor_thread is None or not self._processor_thread.is_alive()):
            self.set_window(self._window)
    
    def shutdown(self):
        """Shutdown the UI bridge gracefully."""
        self._shutdown = True
        if self._processor_thread:
            # We don't join here to avoid blocking the caller (usually main thread on exit)
            # Daemon=True ensures it dies with the process
            self._processor_thread = None


# Global singleton instance
_ui_bridge = ThreadSafeUIBridge()


def get_ui_bridge() -> ThreadSafeUIBridge:
    """Get the global UI bridge instance."""
    return _ui_bridge
