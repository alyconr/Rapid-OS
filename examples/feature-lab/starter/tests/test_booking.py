import unittest
from booking import BookingSystem

class TestBookingSystem(unittest.TestCase):
    def setUp(self):
        self.system = BookingSystem()

    def test_create_booking_success(self):
        b = self.system.create_booking("user-1", "2026-10-10T10:00")
        self.assertEqual(b["id"], 1)
        self.assertEqual(b["user_id"], "user-1")
        self.assertEqual(b["slot"], "2026-10-10T10:00")
        self.assertEqual(len(self.system.list_bookings()), 1)

    def test_reject_empty_parameters(self):
        with self.assertRaises(ValueError):
            self.system.create_booking("", "2026-10-10T10:00")
        with self.assertRaises(ValueError):
            self.system.create_booking("user-1", "")

if __name__ == "__main__":
    unittest.main()
