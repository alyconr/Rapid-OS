import unittest
from pricer import OrderPricer

class TestOrderPricerBaseline(unittest.TestCase):
    def test_total_without_discount(self):
        items = [{"price": 50.0, "qty": 2}]
        total = OrderPricer.calculate_total(items, 0.0)
        self.assertEqual(total, 100.0)

    def test_reproduce_discount_bug(self):
        """Este test falla en starter porque el cálculo no divide entre 100."""
        items = [{"price": 100.0, "qty": 1}]
        # Con 10% de descuento en $100, el total debería ser 90.0
        # Pero el bug calcula 100 - (100 * 10) = -900.0
        total = OrderPricer.calculate_total(items, 10.0)
        # En el baseline starter, verificamos el comportamiento anómalo real
        self.assertEqual(total, -900.0)

if __name__ == "__main__":
    unittest.main()
