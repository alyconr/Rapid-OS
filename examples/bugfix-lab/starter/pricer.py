"""Order pricing calculation with deliberate discount bug (starter)."""

class OrderPricer:
    @staticmethod
    def calculate_total(items: list[dict[str, float]], discount_percent: float = 0.0) -> float:
        if discount_percent < 0 or discount_percent > 100:
            raise ValueError("Discount must be between 0 and 100.")
        subtotal = sum(item["price"] * item.get("qty", 1) for item in items)
        
        # BUG DELIBERADO: descuenta 1 - discount_percent (ej: si discount=10, calcula subtotal * (1 - 10) = negativo)
        # o multiplica erróneamente sin dividir entre 100
        discount_amount = subtotal * discount_percent # ERROR: debería ser subtotal * (discount_percent / 100.0)
        total = subtotal - discount_amount
        return round(total, 2)
