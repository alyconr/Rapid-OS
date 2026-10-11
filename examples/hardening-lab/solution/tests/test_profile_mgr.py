import unittest
from profile_mgr import UserProfileManager, ValidationError

class TestUserProfileHardened(unittest.TestCase):
    def setUp(self):
        self.mgr = UserProfileManager()

    def test_valid_profile(self):
        p = self.mgr.register_user("alice_99", "alice@corp.test", "Developer bio")
        self.assertEqual(p["username"], "alice_99")
        self.assertEqual(p["email"], "alice@corp.test")

    def test_reject_short_or_invalid_username(self):
        with self.assertRaises(ValidationError):
            self.mgr.register_user("al", "al@test.com", "Bio")
        with self.assertRaises(ValidationError):
            self.mgr.register_user("bad user!", "al@test.com", "Bio")

    def test_reject_invalid_email(self):
        with self.assertRaises(ValidationError):
            self.mgr.register_user("valid_user", "not-an-email", "Bio")

    def test_reject_oversized_or_null_byte_bio(self):
        with self.assertRaises(ValidationError):
            self.mgr.register_user("valid_user", "valid@test.com", "a" * 201)
        with self.assertRaises(ValidationError):
            self.mgr.register_user("valid_user", "valid@test.com", "bad\x00bio")

if __name__ == "__main__":
    unittest.main()
