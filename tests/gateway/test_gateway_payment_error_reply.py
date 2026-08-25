"""Billing/credit provider errors must produce a billing reply, not auth.

Field report: a zero-balance OpenAI account returns "You have no credits
remaining..." under a 401 envelope. The gateway's auth branch matched the 401
and replied "Provider authentication failed. Check the configured
credentials", so the operator rotated credentials that were never the
problem. Billing language must be classified before the auth and rate-limit
branches.
"""

from gateway.run import (
    _GATEWAY_PAYMENT_ERROR_RE,
    _gateway_provider_error_reply,
    _looks_like_gateway_provider_error,
)


class TestGatewayPaymentErrorReply:
    def test_zero_balance_401_reports_billing_not_auth(self):
        text = (
            "Error code: 401 - {'error': {'message': 'You have no credits "
            "remaining. Add credits to continue using the API at "
            "https://platform.openai.com/settings/organization/billing/.'}}"
        )
        assert _looks_like_gateway_provider_error(text)
        reply = _gateway_provider_error_reply(text)
        assert "billing" in reply.lower()
        assert "credits" in reply.lower()
        assert "authentication failed" not in reply.lower()

    def test_insufficient_quota_reports_billing_not_rate_limit(self):
        text = (
            "Error code: 429 - {'error': {'message': 'You exceeded your "
            "current quota, please check your plan and billing details.', "
            "'code': 'insufficient_quota'}}"
        )
        reply = _gateway_provider_error_reply(text)
        assert "billing" in reply.lower()
        assert "rate-limiting" not in reply.lower()

    def test_plain_auth_failure_still_reports_auth(self):
        reply = _gateway_provider_error_reply("provider authentication failed")
        assert "authentication" in reply.lower()
        assert "billing" not in reply.lower()

    def test_true_rate_limit_still_reports_rate_limit(self):
        reply = _gateway_provider_error_reply("rate limited after 3 retries")
        assert "rate-limiting" in reply.lower()

    def test_payment_regex_ignores_non_billing_errors(self):
        for text in (
            "HTTP 500 internal server error",
            "provider authentication failed",
            "Errno 111 Connection refused",
            "Rate limited after 3 retries",
        ):
            assert not _GATEWAY_PAYMENT_ERROR_RE.search(text), text
