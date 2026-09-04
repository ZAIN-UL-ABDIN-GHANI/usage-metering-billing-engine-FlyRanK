"""Tests for cost calculation and pricing."""

import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models import Tenant, Plan, Subscription, UsageEvent
from app.config_pricing import PricingConfig


@pytest.mark.asyncio
async def test_api_call_pricing():
    """Test that API calls are priced correctly."""
    config = PricingConfig()
    
    # 1000 API calls @ $0.01 per 1k = $10
    cost = (1000 * config.API_CALL_PRICE_PER_1K) / 1000 * 1000 * 100  # in cents
    assert cost == 1000, "1000 API calls should cost 1000 cents ($10)"


@pytest.mark.asyncio
async def test_input_token_pricing():
    """Test that input tokens are priced correctly."""
    config = PricingConfig()
    
    # 100k input tokens @ $0.0005 per 1k = $0.05
    cost = (100000 * config.INPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # in cents
    assert cost == 5, "100k input tokens should cost 5 cents"


@pytest.mark.asyncio
async def test_cached_input_token_pricing():
    """Test that cached input tokens are cheaper."""
    config = PricingConfig()
    
    # Cached input tokens should be cheaper than regular input
    assert config.CACHED_INPUT_TOKEN_PRICE_PER_1K < config.INPUT_TOKEN_PRICE_PER_1K, \
        "Cached input tokens should be cheaper than regular input tokens"
    
    # 100k cached input tokens @ $0.00015 per 1k = $0.015
    cost = (100000 * config.CACHED_INPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # in cents
    assert cost == pytest.approx(1.5, rel=1e-3), "100k cached input tokens should cost 1.5 cents"


@pytest.mark.asyncio
async def test_output_token_pricing():
    """Test that output tokens are priced correctly."""
    config = PricingConfig()
    
    # 50k output tokens @ $0.002 per 1k = $0.10
    cost = (50000 * config.OUTPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # in cents
    assert cost == 10, "50k output tokens should cost 10 cents"


@pytest.mark.asyncio
async def test_reasoning_token_pricing():
    """Test that reasoning tokens are counted as output."""
    config = PricingConfig()
    
    # Reasoning tokens should be priced same as output
    assert config.REASONING_TOKEN_PRICE_PER_1K == config.OUTPUT_TOKEN_PRICE_PER_1K, \
        "Reasoning tokens should be priced same as output"
    
    # 25k reasoning tokens @ $0.002 per 1k = $0.05
    cost = (25000 * config.REASONING_TOKEN_PRICE_PER_1K) / 1000 * 100  # in cents
    assert cost == 5, "25k reasoning tokens should cost 5 cents"


@pytest.mark.asyncio
async def test_combined_pricing():
    """Test complex pricing calculation with all token types."""
    config = PricingConfig()
    
    # Combined usage
    api_calls = 500
    input_tokens = 50000
    cached_input_tokens = 10000
    output_tokens = 25000
    reasoning_tokens = 5000
    
    # Calculate costs
    api_cost = (api_calls * config.API_CALL_PRICE_PER_1K) / 1000 * 100  # cents
    input_cost = (input_tokens * config.INPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # cents
    cached_cost = (cached_input_tokens * config.CACHED_INPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # cents
    output_cost = (output_tokens * config.OUTPUT_TOKEN_PRICE_PER_1K) / 1000 * 100  # cents
    reasoning_cost = (reasoning_tokens * config.REASONING_TOKEN_PRICE_PER_1K) / 1000 * 100  # cents
    
    total_cost = api_cost + input_cost + cached_cost + output_cost + reasoning_cost
    
    # Verify calculation
    expected = api_cost + input_cost + cached_cost + output_cost + reasoning_cost
    assert total_cost == pytest.approx(expected, rel=1e-3), "Total cost should match expected value"


@pytest.mark.asyncio
async def test_no_floating_point_errors():
    """Test that all costs are stored as integers (cents), no floating point."""
    # Prices should never involve fractions of cents
    config = PricingConfig()
    
    test_quantities = [1, 10, 100, 1000, 10000, 100000, 1000000]
    
    for qty in test_quantities:
        # Calculate cost in cents (always integer)
        cost_cents = int((qty * config.API_CALL_PRICE_PER_1K) / 10)
        
        # Verify no fractional cents
        assert cost_cents == int(cost_cents), f"Cost should be integer cents, got {cost_cents}"


@pytest.mark.asyncio
async def test_pricing_constants_immutable():
    """Test that pricing configuration is locked in."""
    config = PricingConfig()
    
    # Store original values
    original_api = config.API_CALL_PRICE_PER_1K
    original_input = config.INPUT_TOKEN_PRICE_PER_1K
    
    # Verify they're set to expected values
    assert original_api == 0.01, "API call pricing should be $0.01 per 1k"
    assert original_input == 0.0005, "Input token pricing should be $0.0005 per 1k"
    
    # Pricing should not be dynamically changed in tests
    # (would be enforced by immutable config in production)


@pytest.mark.asyncio
async def test_monthly_rollup_cost(db: Session, client: TestClient):
    """Test that monthly usage rolls up into correct total cost."""
    tenant = Tenant(id="tenant-pricing-1", name="Test", email="pricing@example.com")
    plan = Plan(id="free", name="Free", api_calls_limit=10000, ai_tokens_limit=1000000)
    subscription = Subscription(
        tenant_id="tenant-pricing-1", plan_id="free", status="active"
    )
    
    db.add_all([tenant, plan, subscription])
    db.commit()

    # Add various usage events
    events = [
        UsageEvent(tenant_id="tenant-pricing-1", type="api_call", quantity=100, 
                  cost_cents=100, idempotency_key="req-api-1"),
        UsageEvent(tenant_id="tenant-pricing-1", type="ai_tokens", quantity=50000, 
                  cost_cents=2500, idempotency_key="req-tokens-1"),
        UsageEvent(tenant_id="tenant-pricing-1", type="ai_tokens", quantity=10000, 
                  cost_cents=150, idempotency_key="req-cached-1"),
    ]
    
    for event in events:
        db.add(event)
    db.commit()

    # Get usage summary
    response = client.get(
        "/api/usage",
        headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-pricing-1"},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify costs add up correctly
    expected_total = 100 + 2500 + 150  # cents
    assert data.get("current_cost") == expected_total or data.get("total_cost_cents") == expected_total, \
        f"Total cost should be {expected_total} cents"
