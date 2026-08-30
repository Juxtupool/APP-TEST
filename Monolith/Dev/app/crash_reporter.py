import sys
import threading
import traceback
import platform
import time
import json
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from .version import APP_VERSION

logger = logging.getLogger(__name__)

class CrashReporter:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CrashReporter, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, pb_url: Optional[str] = None):
        if getattr(self, '_initialized', False):
            if pb_url:
                self.pb_url = pb_url.rstrip('/')
            return

        self._initialized = True
        self.pb_url = (pb_url or self._load_pb_url_from_config()).rstrip('/')
        self._recent_errors = {}
        self._dedup_lock = threading.Lock()
        self._session = requests.Session()

    def _load_pb_url_from_config(self) -> str:
        default_url = "http://104.197.204.47:8080"
        try:
            # Look for config.json in app root or next to exe
            config_candidates = [
                Path(__file__).parent.parent / "config.json",
                Path(sys.executable).parent / "config.json" if getattr(sys, 'frozen', False) else None
            ]
            for p in config_candidates:
                if p and p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                        url = cfg.get('pocketbase', {}).get('url')
                        if url:
                            return url
        except Exception as e:
            logger.debug(f"CrashReporter config load notice: {e}")
        return default_url

    def set_pb_url(self, url: str):
        if url:
            self.pb_url = url.rstrip('/')

    def _get_os_info(self) -> str:
        try:
            return f"Windows {platform.version()} ({platform.machine()})"
        except Exception:
            return platform.platform()

    def report_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: str,
        source: str = "backend_main",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record error locally and send telemetry to PocketBase asynchronously.
        """
        # Deduplication check (avoid flooding on repeat exceptions)
        dedup_key = f"{source}:{error_type}:{error_message}"
        now = time.time()
        with self._dedup_lock:
            last_sent = self._recent_errors.get(dedup_key, 0)
            if now - last_sent < 60:
                logger.debug(f"Throttling duplicate crash report: {dedup_key}")
                return
            self._recent_errors[dedup_key] = now

        # Clean cache of old keys (> 5 min)
        with self._dedup_lock:
            self._recent_errors = {
                k: v for k, v in self._recent_errors.items() if now - v < 300
            }

        payload = {
            "app_version": APP_VERSION,
            "os_info": self._get_os_info(),
            "error_type": str(error_type)[:100],
            "error_message": str(error_message)[:1000],
            "stack_trace": str(stack_trace)[:10000],
            "source": str(source)[:50],
            "metadata": metadata or {
                "python_version": platform.python_version(),
                "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            }
        }

        # Send asynchronously in a daemon thread so caller is never blocked
        threading.Thread(
            target=self._send_to_pocketbase,
            args=(payload,),
            daemon=True,
            name="CrashReportSender"
        ).start()

    def _send_to_pocketbase(self, payload: Dict[str, Any]):
        if not self.pb_url:
            return

        endpoint = f"{self.pb_url}/api/collections/crash_reports/records"
        try:
            resp = self._session.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            if resp.status_code in (200, 201):
                logger.info(f"Crash report telemetry successfully submitted to PocketBase (id: {resp.json().get('id')})")
            else:
                logger.warning(f"PocketBase crash report submission status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            # Never raise during crash reporting
            logger.debug(f"Could not send crash report to PocketBase: {e}")

    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """Global sys.excepthook handler."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        formatted_trace = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Uncaught Exception (Main Thread):\n{formatted_trace}")

        self.report_error(
            error_type=exc_type.__name__ if hasattr(exc_type, '__name__') else str(exc_type),
            error_message=str(exc_value),
            stack_trace=formatted_trace,
            source="backend_main"
        )

    def handle_thread_exception(self, args):
        """Global threading.excepthook handler (Python 3.8+)."""
        if issubclass(args.exc_type, KeyboardInterrupt):
            return

        formatted_trace = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_tb))
        thread_name = args.thread.name if args.thread else "UnknownThread"
        logger.critical(f"Uncaught Exception in thread '{thread_name}':\n{formatted_trace}")

        self.report_error(
            error_type=args.exc_type.__name__ if hasattr(args.exc_type, '__name__') else str(args.exc_type),
            error_message=str(args.exc_value),
            stack_trace=formatted_trace,
            source=f"backend_thread:{thread_name}"
        )

# Singleton instance
crash_reporter = CrashReporter()

def init_crash_reporter(pb_url: Optional[str] = None):
    """Register global exception hooks and initialize reporter."""
    global crash_reporter
    if pb_url:
        crash_reporter.set_pb_url(pb_url)

    # Attach sys excepthook
    sys.excepthook = crash_reporter.handle_uncaught_exception

    # Attach threading excepthook if available
    if hasattr(threading, 'excepthook'):
        threading.excepthook = crash_reporter.handle_thread_exception

    logger.info("Global crash reporting and exception hooks initialized.")
    return crash_reporter
