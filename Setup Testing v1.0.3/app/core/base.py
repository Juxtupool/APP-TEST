import logging
import functools
import traceback
from typing import Any, Dict, Optional, Union

# Configure a base logger
logger = logging.getLogger("Macropad.Core")

class BackendError(Exception):
    """Base exception for known backend errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error

class ApiResponse:
    """Helper for consistent API responses."""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """Return a standardized success response."""
        response = {"status": "success"}
        if data is not None:
            response["data"] = data
        if message:
            response["message"] = message
        return response

    @staticmethod
    def error(message: str, error_code: str = "UNKNOWN_ERROR", details: Any = None) -> Dict[str, Any]:
        """Return a standardized error response."""
        response = {
            "status": "error",
            "message": message,
            "code": error_code
        }
        if details:
            response["details"] = details
        return response

def safe_api(func):
    """
    Decorator to wrap API methods.
    - Logs entry and exit.
    - Catches exceptions and returns a formatted error response.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__
        class_name = args[0].__class__.__name__ if args else "Unknown"
        
        # logger.debug(f"Calling API: {class_name}.{method_name}")
        
        try:
            result = func(*args, **kwargs)
            return result
        except BackendError as be:
            logger.error(f"BackendError in {class_name}.{method_name}: {be}")
            return ApiResponse.error(str(be), error_code="BACKEND_ERROR")
        except Exception as e:
            logger.error(f"Unhandled Exception in {class_name}.{method_name}: {e}")
            logger.error(traceback.format_exc())
            return ApiResponse.error(
                message=f"An unexpected error occurred: {str(e)}",
                error_code="INTERNAL_SERVER_ERROR",
                details=traceback.format_exc()
            )
            
    return wrapper

class BaseService:
    """Base class for all services."""
    def __init__(self):
        self.logger = logging.getLogger(f"Macropad.Service.{self.__class__.__name__}")
        self.logger.info(f"Initializing {self.__class__.__name__}")

class BaseHandler:
    """Base class for all handlers/mixins."""
    pass
