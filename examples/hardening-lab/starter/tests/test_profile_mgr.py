import unittest
from profile_mgr import UserProfileManager

class TestUserProfileBaseline(unittest.TestCase):
    def test_basic_registration(self):
        mgr = UserProfileManager()
        p = mgr.register_user("alice", "alice@example.com", "Dev")
        self.assertEqual(p["username"], "alice")
        self.assertEqual(p["email"], "alice@example.com")

if __name__ == "__main__":
    unittest.main()
