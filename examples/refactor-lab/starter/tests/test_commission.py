import unittest
from commission import CommissionReporter

class TestCommissionReporter(unittest.TestCase):
    def test_calculate_and_format(self):
        report = CommissionReporter.calculate_and_format(1000.0, 10.0)
        self.assertEqual(report, "[COMMISSION-REPORT] Sales: $1000.00 | Rate: 10.0% | Due: $100.00")

    def test_reject_negative_values(self):
        with self.assertRaises(ValueError):
            CommissionReporter.calculate_and_format(-100.0, 5.0)

if __name__ == "__main__":
    unittest.main()
