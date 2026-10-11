"""Commission calculation tightly coupled with console formatting (starter)."""

class CommissionReporter:
    @staticmethod
    def calculate_and_format(sales_amount: float, rate_percent: float) -> str:
        if sales_amount < 0 or rate_percent < 0:
            raise ValueError("Sales amount and rate must be non-negative.")
        commission = sales_amount * (rate_percent / 100.0)
        # Lógica de cálculo acoplada directamente al formato de visualización
        return f"[COMMISSION-REPORT] Sales: ${sales_amount:.2f} | Rate: {rate_percent:.1f}% | Due: ${commission:.2f}"
