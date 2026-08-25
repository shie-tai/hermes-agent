"""Billing/credit exhaustion must not be reported as authentication.

Field report: an OpenAI account at zero balance returns "You have no credits
remaining. Add credits to continue..." under a 401/429 envelope. The
summarizer's 401/403 branch labeled it "provider authentication error",
sending the operator to rotate credentials (Slack tokens, API keys) that were
never the problem. Billing language must classify as billing, ahead of both
the auth branch (401 envelopes) and the rate-limit branch
("insufficient_quota" payloads contain "quota"/"429").
"""

import pytest

import cron.scheduler as scheduler
from cron.scheduler import _summarize_cron_failure_for_delivery

JOB = {"name": "daily-digest", "id": "abc123", "no_agent": False}


@pytest.fixture(autouse=True)
def _configured_fallback_chain(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "load_config",
        lambda: {"fallback_providers": [{"provider": "nous", "model": "x"}]},
    )
    monkeypatch.setattr(
        scheduler,
        "get_fallback_chain",
        lambda cfg: [{"provider": "nous", "model": "x"}],
    )


@pytest.mark.parametrize(
    "error",
    [
        # OpenAI zero prepaid balance — rides a 401 envelope, must beat the
        # auth branch.
        "Error code: 401 - {'error': {'message': 'You have no credits "
        "remaining. Add credits to continue using the API at "
        "https://platform.openai.com/settings/organization/billing/.'}}",
        # OpenAI insufficient_quota — contains 429 + quota, must beat the
        # rate-limit branch.
        "Error code: 429 - {'error': {'message': 'You exceeded your current "
        "quota, please check your plan and billing details.', "
        "'code': 'insufficient_quota'}}",
        # OpenRouter 402.
        "Error code: 402 - Insufficient credits. Add more using "
        "https://openrouter.ai/settings/credits",
        # Anthropic low balance.
        "Your credit balance is too low to access the Anthropic API.",
    ],
)
def test_billing_errors_classified_as_billing_not_auth(error):
    msg = _summarize_cron_failure_for_delivery(JOB, error)
    assert "billing/credits error" in msg
    assert "not an authentication problem" in msg
    assert "provider authentication error" not in msg


def test_plain_401_still_classified_as_authentication():
    msg = _summarize_cron_failure_for_delivery(JOB, "HTTP 401 authentication failed")
    assert "provider authentication error" in msg
    assert "billing" not in msg.lower()


def test_permission_403_names_missing_model_access():
    """A 403 entitlement rejection must point at account access, not just
    credentials — the Nous portal phrases entitlement gaps as 'you don't have
    permissions', which no amount of credential rotation fixes."""
    msg = _summarize_cron_failure_for_delivery(
        JOB,
        "Error code: 403 - {'status': 403, 'message': \"You tried to access "
        "something that you don't have permissions for.\"}",
    )
    assert "provider authentication error" in msg
    assert "lacks access" in msg


def test_true_rate_limit_still_classified_as_rate_limit():
    msg = _summarize_cron_failure_for_delivery(
        JOB, "Error code: 429 - Rate limit reached, try again in 20s"
    )
    assert "provider rate limit" in msg
    assert "billing" not in msg.lower()


def test_no_agent_script_billing_prose_never_blamed_on_provider():
    """The mode gate outranks billing language: a script's own prose about
    credits must not produce a provider-billing alert for a job that never
    opened a provider socket."""
    job = {"name": "nightly", "no_agent": True, "script": "s.py"}
    msg = _summarize_cron_failure_for_delivery(
        job, "Script failed: customer billing export had no credits column"
    )
    assert "provider" not in msg.lower()
