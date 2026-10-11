import unittest
from commission import CommissionCalculator, CommissionReporter

class TestCommissionRefactored(unittest.TestCase):
    def test_calculator_isolated_domain_logic(self):
        result = CommissionCalculator.calculate(1500.0, 12.5)
        self.assertEqual(result, 187.5)

    def test_reporter_backwards_compatibility(self):
        report = CommissionReporter.calculate_and_format(1000.0, 10.0)
        self.assertEqual(report, "[COMMISSION-REPORT] Sales: $1000.00 | Rate: 10.0% | Due: $100.00")

    def test_rejections(self):
        with self.assertRaises(ValueError):
            CommissionCalculator.calculate(-50.0, 10.0)
        with self.assertRaises(ValueError):
            CommissionReporter.calculate_and_format(100.0, -1.0)

if __name__ == "__main__":
    unittest.main()
