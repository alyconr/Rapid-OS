import unittest
from pricer import OrderPricer

class TestOrderPricerBaseline(unittest.TestCase):
    def test_total_without_discount(self):
        items = [{"price": 50.0, "qty": 2}]
        total = OrderPricer.calculate_total(items, 0.0)
        self.assertEqual(total, 100.0)

    def test_defect_characterization(self):
        """Caracterización del defecto: documenta el comportamiento anómalo real en el starter."""
        items = [{"price": 100.0, "qty": 1}]
        # En el código starter defectuoso, 100 - (100 * 10) = -900.0
        total = OrderPricer.calculate_total(items, 10.0)
        self.assertEqual(total, -900.0)

    def test_regression_expected_discount(self):
        """Prueba de regresión: exige el comportamiento correcto (10% de $100 = $90). Falla en starter."""
        items = [{"price": 100.0, "qty": 1}]
        total = OrderPricer.calculate_total(items, 10.0)
        self.assertEqual(total, 90.0)

if __name__ == "__main__":
    unittest.main()

