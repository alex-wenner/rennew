from rennew.telemetry.pricing import calculate_cost, get_model_pricing


def test_model_pricing_lookup() -> None:
    sonnet = get_model_pricing("anthropic/claude-sonnet-5")
    assert sonnet.input_per_m == 2.0
    assert sonnet.output_per_m == 10.0

    terra = get_model_pricing("openai/gpt-5.6-terra")
    assert terra.input_per_m == 2.0
    assert terra.output_per_m == 12.0


def test_calculate_cost() -> None:
    cost = calculate_cost(
        "gpt-5.6-terra",
        input_tokens=10_000,
        output_tokens=2_000,
        reasoning_tokens=1_000,
    )
    assert round(cost, 4) == 0.056
