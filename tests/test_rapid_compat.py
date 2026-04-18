import unittest

import rapid


class RapidCompatibilityTests(unittest.TestCase):
    def test_compatibility_constants_are_reexported(self):
        self.assertTrue(hasattr(rapid, "SCRIPT_DIR"))
        self.assertTrue(hasattr(rapid, "TEMPLATES_DIR"))
        self.assertTrue(hasattr(rapid, "CURRENT_DIR"))
        self.assertTrue(hasattr(rapid, "PROJECT_RAPID_DIR"))
        self.assertTrue(hasattr(rapid, "CONFIG_FILE"))

    def test_compatibility_helpers_are_reexported(self):
        self.assertTrue(callable(rapid.load_project_config))
        self.assertTrue(callable(rapid.save_project_config))
        self.assertTrue(callable(rapid.create_backup))
        self.assertTrue(callable(rapid.regenerate_context))
        self.assertTrue(callable(rapid.main))


if __name__ == "__main__":
    unittest.main()

