"""Decoupled commission calculation and formatting (solution)."""

class CommissionCalculator:
    """Pure domain logic for commission calculation."""
    @staticmethod
    def calculate(sales_amount: float, rate_percent: float) -> float:
        if sales_amount < 0 or rate_percent < 0:
            raise ValueError("Sales amount and rate must be non-negative.")
        return round(sales_amount * (rate_percent / 100.0), 2)

class CommissionReporter:
    """Presentation layer preserving backwards-compatible public API."""
    @staticmethod
    def calculate_and_format(sales_amount: float, rate_percent: float) -> str:
        commission = CommissionCalculator.calculate(sales_amount, rate_percent)
        return f"[COMMISSION-REPORT] Sales: ${sales_amount:.2f} | Rate: {rate_percent:.1f}% | Due: ${commission:.2f}"
