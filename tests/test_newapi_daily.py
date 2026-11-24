import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("newapi_daily", ROOT / "newapi_daily.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, payload=None, status=200, text=None, headers=None):
        self.status_code = status
        self.text = (
            text
            if text is not None
            else json.dumps(payload if payload is not None else {})
        )
        self.headers = headers or {}


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.proxies = {}
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.sessions = []

    def __call__(self):
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        session = FakeSession(self.responses.pop(0))
        self.sessions.append(session)
        return session


def status_payload(checked=False, enabled=True):
    return {
        "success": True,
        "data": {
            "enabled": enabled,
            "stats": {
                "checked_in_today": checked,
                "total_checkins": 2,
                "total_quota": 1000,
            },
        },
    }


class AccountParsingTests(unittest.TestCase):
    def test_plain_and_json_accounts(self):
        accounts = MODULE.parse_accounts(
            "主号|https://newapi.example|token-one|42"
        )
        self.assertEqual(accounts[0].user_id, "42")
        accounts = MODULE.parse_accounts(
            json.dumps(
                [
                    {
                        "name": "json",
                        "baseURL": "https://newapi.example",
                        "accessToken": "token-json",
                    }
                ]
            )
        )
        self.assertEqual(accounts[0].label, "json")
        self.assertEqual(accounts[0].access_token, "token-json")

    def test_http_is_rejected_outside_loopback(self):
        with self.assertRaises(MODULE.ConfigError):
            MODULE.normalize_base_url("http://newapi.example")

    def test_host_is_normalized_and_short_email_is_redacted(self):
        self.assertEqual(
            MODULE.normalize_base_url("https://NEWAPI.EXAMPLE"),
            "https://newapi.example",
        )
        self.assertEqual(MODULE.redact_identifier("a@example.com"), "a***@example.com")
        self.assertNotIn("a@example.com", MODULE.sanitize_message("failed for a@example.com"))

    def test_only_ranges(self):
        self.assertEqual(MODULE.parse_only("1,3-4", 5), {1, 3, 4})


class FlowTests(unittest.TestCase):
    def account(self):
        return MODULE.Account(
            name="测试",
            base_url="https://newapi.example",
            access_token="token-secret",
            user_id="42",
        )

    def client(self, *responses, pow_budget=5):
        transport = FakeTransport(*responses)
        client = MODULE.NewAPIClient(
            wait_seconds=0,
            pow_budget=pow_budget,
            session_factory=transport,
        )
        return client, transport

    def test_query_only_never_posts(self):
        client, transport = self.client(FakeResponse(status_payload()))
        result = MODULE.run_account(1, self.account(), client, query_only=True)
        self.assertEqual(result.status, "QUERY")
        self.assertEqual(len(transport.sessions), 1)
        self.assertEqual(transport.sessions[0].calls[0][0], "GET")

    def test_pow_claim_and_readback(self):
        client, transport = self.client(
            FakeResponse(status_payload()),
            FakeResponse(
                {
                    "success": True,
                    "data": {
                        "challenge_id": "challenge-1",
                        "prefix": "prefix-",
                        "difficulty": 0,
                    },
                }
            ),
            FakeResponse(
                {
                    "success": True,
                    "data": {"quota_awarded": 500},
                }
            ),
            FakeResponse(status_payload(checked=True)),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertTrue(result.pow_used)
        self.assertEqual(result.reward_amount, Decimal("500"))
        post_kwargs = transport.sessions[2].calls[0][2]
        self.assertEqual(post_kwargs["params"]["pow_challenge"], "challenge-1")
        self.assertEqual(post_kwargs["params"]["pow_nonce"], "00000000")
        self.assertNotIn("json", post_kwargs)
        self.assertNotIn("data", post_kwargs)

    def test_no_pow_fallback_still_claims(self):
        client, transport = self.client(
            FakeResponse(status_payload()),
            FakeResponse({"success": False}, status=404),
            FakeResponse(
                {
                    "success": True,
                    "data": {"quota_awarded": 500},
                }
            ),
            FakeResponse(status_payload(checked=True)),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertFalse(result.pow_used)
        post_kwargs = transport.sessions[2].calls[0][2]
        self.assertIsNone(post_kwargs["params"])
        self.assertNotIn("json", post_kwargs)
        self.assertNotIn("data", post_kwargs)

    def test_missing_quota_is_unconfirmed(self):
        client, _ = self.client(
            FakeResponse(status_payload()),
            FakeResponse({"success": False}, status=404),
            FakeResponse({"success": True, "data": {}}),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "UNCONFIRMED")
        self.assertIn("quota_awarded", result.message)

    def test_cloudflare_challenge_is_manual_required(self):
        client, _ = self.client(
            FakeResponse(
                status=403,
                text="<html><title>Just a moment...</title></html>",
                headers={"cf-mitigated": "challenge"},
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "MANUAL_REQUIRED")
        self.assertFalse(result.ok)

    def test_false_captcha_field_does_not_trigger_manual_required(self):
        client, _ = self.client(
            FakeResponse(
                {
                    "success": True,
                    "data": {
                        "enabled": True,
                        "requires_captcha": False,
                        "stats": {"checked_in_today": True},
                    },
                }
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "ALREADY")
        self.assertTrue(result.ok)

    def test_chinese_challenge_is_manual_required(self):
        client, _ = self.client(
            FakeResponse(
                {
                    "success": False,
                    "message": "请完成人机验证后重试",
                }
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "MANUAL_REQUIRED")
        self.assertFalse(result.ok)

    def test_disabled_business_response_is_inactive(self):
        client, _ = self.client(
            FakeResponse(
                {
                    "success": False,
                    "message": "Check-in feature is not enabled",
                },
                status=400,
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "INACTIVE")
        self.assertTrue(result.ok)

    def test_pow_refusal_retries_once_with_fresh_challenge(self):
        client, transport = self.client(
            FakeResponse(status_payload()),
            FakeResponse(
                {
                    "success": True,
                    "data": {
                        "challenge_id": "challenge-1",
                        "prefix": "prefix-",
                        "difficulty": 0,
                    },
                }
            ),
            FakeResponse(
                {
                    "success": False,
                    "message": "pow challenge expired",
                },
                status=400,
            ),
            FakeResponse(
                {
                    "success": True,
                    "data": {
                        "challenge_id": "challenge-2",
                        "prefix": "prefix-",
                        "difficulty": 0,
                    },
                }
            ),
            FakeResponse(
                {
                    "success": True,
                    "data": {"quota_awarded": 500},
                }
            ),
            FakeResponse(status_payload(checked=True)),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertTrue(result.pow_used)
        self.assertEqual(len(transport.sessions), 6)
        self.assertEqual(
            transport.sessions[4].calls[0][2]["params"]["pow_challenge"],
            "challenge-2",
        )

    def test_already_checked_in_skips_post(self):
        client, transport = self.client(FakeResponse(status_payload(checked=True)))
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "ALREADY")
        self.assertEqual(len(transport.sessions), 1)

    def test_inactive_site_is_neutral(self):
        client, _ = self.client(FakeResponse(status_payload(enabled=False)))
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "INACTIVE")
        self.assertTrue(result.ok)

    def test_auth_error_is_not_success(self):
        client, _ = self.client(FakeResponse({"success": False}, status=401))
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "AUTH_EXPIRED")
        self.assertFalse(result.ok)

    def test_malformed_status_is_unconfirmed(self):
        client, _ = self.client(FakeResponse({"success": True, "data": {"enabled": True}}))
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "UNCONFIRMED")
        self.assertFalse(result.ok)

    def test_solver_rejects_difficult_challenge_with_tiny_budget(self):
        challenge = MODULE.PowChallenge("c", "p", 256)
        with self.assertRaises(MODULE.APIError):
            MODULE.solve_challenge(challenge, budget_seconds=1)


if __name__ == "__main__":
    unittest.main()
