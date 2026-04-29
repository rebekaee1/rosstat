from app.services.action_policy import SafetyClass, allowed_counter_ids, evaluate_action


def test_allowed_counter_defaults_to_forecast_counter():
    assert "107136069" in allowed_counter_ids()


def test_read_only_action_allowed():
    decision = evaluate_action("analytics.status.read", {"counter_id": "107136069"})
    assert decision.allowed is True
    assert decision.safety_class == SafetyClass.READ_ONLY


def test_non_allowlisted_counter_is_blocked():
    decision = evaluate_action("metrika.goal.create", {"counter_id": "1", "goal": {}})
    assert decision.allowed is False
    assert "allowlist" in decision.reason


def test_delete_counter_is_denied():
    decision = evaluate_action("metrika.counter.delete", {"counter_id": "107136069"}, approved=True)
    assert decision.allowed is False
    assert decision.safety_class == SafetyClass.DENIED


def test_write_requires_live_write_flag_and_approval():
    decision = evaluate_action("webmaster.recrawl.submit", {"host": "forecasteconomy.com", "url": "https://forecasteconomy.com/"})
    assert decision.allowed is False
    assert decision.requires_approval is True
