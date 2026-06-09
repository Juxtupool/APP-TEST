import unittest
import sys
import os

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core import safe_api, ApiResponse, BackendError, BaseService

class TestService(BaseService):
    @safe_api
    def successful_method(self):
        return ApiResponse.success(data="test_data", message="OK")

    @safe_api
    def failing_method(self):
        raise ValueError("Oops")

    @safe_api
    def backend_error_method(self):
        raise BackendError("Custom Backend Error")

    @safe_api
    def successful_method_no_data(self):
        return ApiResponse.success()

class TestFramework(unittest.TestCase):
    def setUp(self):
        self.service = TestService()

    def test_success(self):
        result = self.service.successful_method()
        print(f"Success Result: {result}")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], "test_data")

    def test_success_no_data(self):
        result = self.service.successful_method_no_data()
        self.assertEqual(result["status"], "success")
        # Ensure 'data' key exists even if None, or depends on implementation. 
        # ApiResponse.success implementation: if data is not None it adds it.
        # If I call success(), data is None default.
        # Let's check logic:
        # if data is not None: response["data"] = data
        # So 'data' key might be missing.
        self.assertNotIn("data", result)

    def test_failure_catch(self):
        result = self.service.failing_method()
        print(f"Failure Result: {result}")
        self.assertEqual(result["status"], "error")
        # safe_api catches generic Exception and returns "An unexpected error occurred..."
        # It puts exception string in message? 
        # "message": f"An unexpected error occurred: {str(e)}"
        self.assertTrue("Oops" in result["message"])
        self.assertEqual(result["code"], "INTERNAL_SERVER_ERROR")

    def test_backend_error_catch(self):
        result = self.service.backend_error_method()
        print(f"Backend Error Result: {result}")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Custom Backend Error")
        self.assertEqual(result["code"], "BACKEND_ERROR")
    def test_mixins_methods_decorated(self):
        from app.handlers.profile_handler import ProfileMixin
        from app.handlers.serial_handler import SerialMixin
        from app.handlers.system_handler import SystemMixin
        from app.handlers.community_handler import CommunityMixin
        from app.handlers.icon_handler import IconMixin
        from app.handlers.update_handler import UpdateMixin
        from app.handlers.macro_handler import MacroMixin

        mixins = [
            ProfileMixin,
            SerialMixin,
            SystemMixin,
            CommunityMixin,
            IconMixin,
            UpdateMixin,
            MacroMixin
        ]

        for mixin in mixins:
            for name in dir(mixin):
                if name.startswith('_'):
                    continue
                member = getattr(mixin, name)
                if callable(member):
                    # Verify it has __wrapped__ (meaning safe_api decorated it)
                    self.assertTrue(
                        hasattr(member, '__wrapped__'),
                        f"Public method {mixin.__name__}.{name} is not decorated with @safe_api!"
                    )

if __name__ == '__main__':
    unittest.main()

