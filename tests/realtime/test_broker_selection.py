from terminal.realtime.handler import select_market_providers


def test_select_market_uses_preferred_active_provider() -> None:
    selected = select_market_providers(
        market_candidates={"india": ["upstox", "kite"]},
        broker_tokens={"upstox": "token-a", "kite": "token-b"},
        defaults_map={("realtime_candles", "india"): "kite"},
    )

    assert selected == {"india": "kite"}


def test_select_market_falls_back_to_first_active_when_no_preference() -> None:
    selected = select_market_providers(
        market_candidates={"india": ["upstox", "kite"]},
        broker_tokens={"upstox": "token-a", "kite": "token-b"},
        defaults_map={},
    )

    assert selected == {"india": "upstox"}


def test_select_market_falls_back_to_first_active_when_preferred_inactive() -> None:
    selected = select_market_providers(
        market_candidates={"india": ["upstox", "kite", "ibkr"]},
        broker_tokens={"upstox": "token-a", "kite": None, "ibkr": "token-c"},
        defaults_map={("realtime_candles", "india"): "kite"},
    )

    assert selected == {"india": "upstox"}
