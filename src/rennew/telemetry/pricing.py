from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_per_m: float
    output_per_m: float
    reasoning_per_m: float
    cache_read_per_m: float
    cache_write_per_m: float
    context_limit: int = 200_000


# USD per 1M tokens. Current-generation lineup as of September 2026.
# Verify against official provider pricing pages before relying on cost figures.
PRICING_TABLE: dict[str, ModelPricing] = {
    # OpenAI GPT-5.6 family (GA July 2026, 1.05M context)
    "gpt-5.6-sol": ModelPricing(4.0, 20.0, 20.0, 0.40, 0.0, 1_050_000),
    "gpt-5.6-terra": ModelPricing(2.0, 12.0, 12.0, 0.20, 0.0, 1_050_000),
    "gpt-5.6-luna": ModelPricing(0.20, 1.20, 1.20, 0.02, 0.0, 1_050_000),
    # OpenAI earlier current models
    "gpt-5.5-pro": ModelPricing(30.0, 180.0, 180.0, 3.0, 0.0, 400_000),
    "gpt-5.5": ModelPricing(5.0, 30.0, 30.0, 0.50, 0.0, 400_000),
    "gpt-5.4-pro": ModelPricing(5.0, 30.0, 30.0, 0.50, 0.0, 400_000),
    "gpt-5.4": ModelPricing(2.50, 15.0, 15.0, 0.25, 0.0, 400_000),
    "gpt-5.1": ModelPricing(1.25, 10.0, 10.0, 0.125, 0.0, 400_000),
    "gpt-5-mini": ModelPricing(0.25, 2.0, 2.0, 0.025, 0.0, 128_000),
    "gpt-5-nano": ModelPricing(0.05, 0.40, 0.40, 0.005, 0.0, 128_000),
    # Anthropic current lineup
    "claude-fable-5-1": ModelPricing(10.0, 50.0, 50.0, 1.0, 12.5, 200_000),
    "claude-fable-5": ModelPricing(10.0, 50.0, 50.0, 1.0, 12.5, 200_000),
    "claude-mythos-5-1": ModelPricing(10.0, 50.0, 50.0, 1.0, 12.5, 200_000),
    "claude-opus-5": ModelPricing(5.0, 25.0, 25.0, 0.50, 6.25, 200_000),
    "claude-sonnet-5": ModelPricing(2.0, 10.0, 10.0, 0.20, 2.50, 200_000),
    "claude-haiku-4-5": ModelPricing(1.0, 5.0, 5.0, 0.10, 1.25, 200_000),
    # Open-weight / self-hosted reference rates
    "gpt-oss-120b": ModelPricing(0.15, 0.60, 0.60, 0.015, 0.0, 128_000),
    "gpt-oss-20b": ModelPricing(0.05, 0.20, 0.20, 0.005, 0.0, 128_000),
}

DEFAULT_PRICING = ModelPricing(
    input_per_m=2.0,
    output_per_m=10.0,
    reasoning_per_m=10.0,
    cache_read_per_m=0.20,
    cache_write_per_m=1.0,
    context_limit=200_000,
)


def get_model_pricing(model_name: str | None) -> ModelPricing:
    if not model_name:
        return DEFAULT_PRICING
    key = model_name.lower()
    if key in PRICING_TABLE:
        return PRICING_TABLE[key]
    for candidate, pricing in PRICING_TABLE.items():
        if candidate in key or key in candidate:
            return pricing
    return DEFAULT_PRICING


def calculate_cost(
    model: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    provider: str | None = None,
) -> float:
    """Cost from the live models.dev catalog when available, else the local table."""
    from rennew.providers import modelsdev

    meta = modelsdev.lookup(provider, model or "") if model else None
    if meta is not None:
        cost = (
            (input_tokens / 1_000_000) * meta.input_per_m
            + (output_tokens / 1_000_000) * meta.output_per_m
            + (reasoning_tokens / 1_000_000) * meta.output_per_m
            + (cache_read_tokens / 1_000_000) * meta.cache_read_per_m
            + (cache_write_tokens / 1_000_000) * meta.cache_write_per_m
        )
        return round(cost, 6)
    pricing = get_model_pricing(model)
    cost = (
        (input_tokens / 1_000_000) * pricing.input_per_m
        + (output_tokens / 1_000_000) * pricing.output_per_m
        + (reasoning_tokens / 1_000_000) * pricing.reasoning_per_m
        + (cache_read_tokens / 1_000_000) * pricing.cache_read_per_m
        + (cache_write_tokens / 1_000_000) * pricing.cache_write_per_m
    )
    return round(cost, 6)
