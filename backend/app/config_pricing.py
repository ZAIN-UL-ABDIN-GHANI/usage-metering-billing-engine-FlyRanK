"""Pricing configuration - immutable pricing rules."""


class PricingConfig:
    """Pricing constants for the billing engine.
    
    All prices are in USD per 1,000 units.
    Costs are stored as integers (cents) in database to avoid floating point errors.
    """

    # API Call Pricing
    API_CALL_PRICE_PER_1K = 0.01  # $0.01 per 1,000 API calls

    # AI Token Pricing
    INPUT_TOKEN_PRICE_PER_1K = 0.0005  # $0.0005 per 1,000 input tokens
    CACHED_INPUT_TOKEN_PRICE_PER_1K = 0.00015  # $0.00015 per 1,000 cached input tokens (cheaper)
    OUTPUT_TOKEN_PRICE_PER_1K = 0.002  # $0.002 per 1,000 output tokens
    REASONING_TOKEN_PRICE_PER_1K = 0.002  # $0.002 per 1,000 reasoning tokens (counted as output)

    # Monthly billing cycle
    BILLING_CYCLE_DAYS = 30

    @staticmethod
    def calculate_cost_cents(
        api_calls: int = 0,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> int:
        """Calculate total cost in cents.
        
        Args:
            api_calls: Number of API calls
            input_tokens: Number of input tokens
            cached_input_tokens: Number of cached input tokens (cheaper)
            output_tokens: Number of output tokens
            reasoning_tokens: Number of reasoning tokens (counted as output)

        Returns:
            Total cost in cents (integer)
        """
        config = PricingConfig()
        
        # Calculate each component
        api_cost = (api_calls * config.API_CALL_PRICE_PER_1K) / 10
        input_cost = (input_tokens * config.INPUT_TOKEN_PRICE_PER_1K) / 100
        cached_cost = (cached_input_tokens * config.CACHED_INPUT_TOKEN_PRICE_PER_1K) / 100
        output_cost = (output_tokens * config.OUTPUT_TOKEN_PRICE_PER_1K) / 100
        reasoning_cost = (reasoning_tokens * config.REASONING_TOKEN_PRICE_PER_1K) / 100
        
        # Sum all costs
        total_cents = api_cost + input_cost + cached_cost + output_cost + reasoning_cost
        
        # Return as integer (cents)
        return int(round(total_cents))

    @staticmethod
    def format_cost_dollars(cost_cents: int) -> str:
        """Format cost in cents as dollars string.
        
        Args:
            cost_cents: Cost in cents

        Returns:
            Formatted string like "$10.50"
        """
        dollars = cost_cents / 100
        return f"${dollars:.2f}"


# Pricing constants for Easy Access
PRICING = PricingConfig()
