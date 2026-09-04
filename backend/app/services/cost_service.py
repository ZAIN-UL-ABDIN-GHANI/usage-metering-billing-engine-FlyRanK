from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

class CostService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_cost(
        self,
        api_calls: int = 0,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
        rates: dict | None = None,
    ) -> float:
        """Calculate usage cost in dollars using decimal arithmetic."""
        rates = rates or {
            "api_call": 0.001,
            "input_token": 0.000003,
            "cached_input_token": 0.000015,
            "output_token": 0.000015,
            "reasoning_token": 0.000015,
        }
        total = sum(
            Decimal(str(quantity)) * Decimal(str(rates.get(rate_name, 0)))
            for quantity, rate_name in (
                (api_calls, "api_call"),
                (input_tokens, "input_token"),
                (cached_input_tokens, "cached_input_token"),
                (output_tokens, "output_token"),
                (reasoning_tokens, "reasoning_token"),
            )
        )
        return float(total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))