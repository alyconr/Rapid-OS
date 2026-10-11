import unittest
from pricer import OrderPricer

class TestOrderPricerSolution(unittest.TestCase):
    def test_total_without_discount(self):
        items = [{"price": 50.0, "qty": 2}]
        total = OrderPricer.calculate_total(items, 0.0)
        self.assertEqual(total, 100.0)

    def test_correct_discount_calculation(self):
        items = [{"price": 100.0, "qty": 1}]
        total = OrderPricer.calculate_total(items, 10.0)
        self.assertEqual(total, 90.0)

    def test_multiple_items_with_discount(self):
        items = [
            {"price": 40.0, "qty": 2}, # 80
            {"price": 20.0, "qty": 1}, # 20 -> subtotal 100
        ]
        total = OrderPricer.calculate_total(items, 25.0) # 25% desc -> 75.0
        self.assertEqual(total, 75.0)

    def test_reject_out_of_bounds_discount(self):
        items = [{"price": 10.0, "qty": 1}]
        with self.assertRaises(ValueError):
            OrderPricer.calculate_total(items, -5.0)
        with self.assertRaises(ValueError):
            OrderPricer.calculate_total(items, 105.0)

if __name__ == "__main__":
    unittest.main()
