#!/usr/bin/env python3
"""New API daily check-in runner with PoW support and strict readback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests


VERSION = "1.0.0"
PROVIDER = "newapi"
CHECKIN_PATH = "/api/user/checkin"
POW_PATH = "/api/user/pow/challenge"

ACCOUNTS_ENV = "NEWAPI_ACCOUNTS"
ACCOUNT_FILE_ENV = "NEWAPI_ACCOUNT_FILE"
BASE_URL_ENV = "NEWAPI_BASE_URL"
ACCESS_TOKEN_ENV = "NEWAPI_ACCESS_TOKEN"
USER_ID_ENV = "NEWAPI_USER_ID"
PROXY_ENV = "NEWAPI_PROXY"
WAIT_ENV = "NEWAPI_WAIT_SECONDS"
DEFAULT_ACCOUNT_FILE = "newapi_accounts.txt"

DEFAULT_TIMEOUT = 20.0
DEFAULT_WAIT_SECONDS = 0.5
DEFAULT_POW_BUDGET = 60.0
SUCCESS_STATUSES = {"CLAIMED", "ALREADY", "QUERY", "INACTIVE"}
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?(1[3-9]\d{9})(?!\d)")
EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])"
)


class NewAPIError(Exception):
    """Base class for controlled New API errors."""


class ConfigError(NewAPIError):
    """Account or command configuration is invalid."""


class SessionExpired(NewAPIError):
    """The New API access token is no longer accepted."""


class ManualRequired(NewAPIError):
    """The site requires a captcha or another browser challenge."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class APIError(NewAPIError):
    """The service returned an HTTP, JSON, or business error."""

    def __init__(self, message: str, *, status: int = 0, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Account:
    name: str
    base_url: str
    access_token: str
    user_id: str = ""

    @property
    def label(self) -> str:
        return redact_identifier(self.name or self.user_id or self.base_url)

    @property
    def fingerprint(self) -> Tuple[str, str]:
        return (self.base_url, self.user_id or self.access_token)


@dataclass
class CheckinStatus:
    enabled: bool
    checked_in_today: bool
    reward_amount: Optional[Decimal] = None
    total_count: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None


@dataclass
class PowChallenge:
    challenge_id: str
    prefix: str
    difficulty: int
    expires_at: float = 0.0


@dataclass
class RunResult:
    index: int
    label: str
    status: str
    message: str
    http_status: int = 0
    reward_amount: Optional[Decimal] = None
    total_count: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    pow_used: bool = False
    detail_lines: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in SUCCESS_STATUSES

    def as_dict(self) -> Dict[str, Any]:
        return {
            "type": "account",
            "provider": PROVIDER,
            "index": self.index,
            "label": self.label,
            "status": self.status,
            "ok": self.ok,
            "message": self.message,
            "http_status": self.http_status,
            "reward_amount": format_decimal(self.reward_amount),
            "total_count": format_decimal(self.total_count),
            "total_amount": format_decimal(self.total_amount),
            "pow_used": self.pow_used,
            "details": list(self.detail_lines),
        }


def emit(payload: Dict[str, Any]) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
        flush=True,
    )


def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def redact_phone(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        phone = match.group(1)
        return "%s****%s" % (phone[:3], phone[-4:])

    return PHONE_PATTERN.sub(replace, str(text or ""))


def redact_email(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        local, domain = match.group(1), match.group(2)
        visible = local[:1] if local else "*"
        return "%s***@%s" % (visible, domain)

    return EMAIL_PATTERN.sub(replace, str(text or ""))


def redact_identifier(value: Any) -> str:
    text = redact_phone(redact_email(str(value or "").strip()))
    return text[:120] or "NewAPI"


def sanitize_message(message: Any, account: Optional[Account] = None) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " ").strip()
    if account is not None and account.access_token:
        text = text.replace(account.access_token, "[redacted-token]")
    for name in (
        "PUSHPLUS_TOKEN",
        "BARK_URL",
        "WECOM_WEBHOOK",
        "DINGTALK_WEBHOOK",
        "GENERIC_WEBHOOK_URL",
        PROXY_ENV,
    ):
        value = env_text(name)
        if value:
            text = text.replace(value, "[redacted-%s]" % name.lower())
    return redact_phone(redact_email(text))[:800]


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def format_decimal(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def normalize_token(value: Any) -> str:
    token = str(value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token or any(char.isspace() for char in token):
        return ""
    if any(ord(char) < 32 or ord(char) == 127 for char in token):
        return ""
    return token


def is_loopback(hostname: str) -> bool:
    host = str(hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1", "[::1]"}


def normalize_base_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048:
        raise ConfigError("New API base URL is empty or too long")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("New API base URL must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("New API base URL cannot contain credentials, query, or fragment")
    if parsed.scheme == "http" and not is_loopback(parsed.hostname or ""):
        raise ConfigError("New API only allows http for loopback test sites")
    path = (parsed.path or "").rstrip("/")
    if any(segment in {".", ".."} for segment in path.split("/") if segment):
        raise ConfigError("New API base URL contains traversal")
    return "%s://%s%s" % (parsed.scheme, parsed.netloc.lower(), path)


def _json_accounts(value: Any) -> List[Account]:
    items = value.get("accounts") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ConfigError("NEWAPI account JSON must be a list or an object with accounts[]")
    accounts: List[Account] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        base = normalize_base_url(item.get("baseURL") or item.get("base") or item.get("site"))
        token = normalize_token(
            item.get("accessToken")
            or item.get("access_token")
            or item.get("token")
            or item.get("key")
        )
        if not token:
            continue
        name = str(item.get("name") or item.get("label") or item.get("note") or "").strip()
        user_id = str(item.get("userId") or item.get("user_id") or item.get("uid") or "").strip()
        accounts.append(
            Account(name=name, base_url=base, access_token=token, user_id=user_id)
        )
    return accounts


def parse_accounts(raw: str) -> List[Account]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            return _json_accounts(json.loads(text))
        except json.JSONDecodeError as error:
            raise ConfigError("NEWAPI account JSON is invalid: %s" % error) from error

    accounts: List[Account] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if len(parts) not in (3, 4):
            raise ConfigError(
                "NEWAPI account line %d must be label|baseURL|accessToken|userId"
                % line_number
            )
        name, base, token = parts[:3]
        user_id = parts[3].strip() if len(parts) == 4 else ""
        normalized = normalize_token(token)
        if not normalized:
            raise ConfigError("NEWAPI account line %d has no valid token" % line_number)
        accounts.append(
            Account(
                name=name.strip(),
                base_url=normalize_base_url(base),
                access_token=normalized,
                user_id=user_id,
            )
        )
    return accounts


def load_accounts(account_file: Optional[str] = None) -> List[Account]:
    raw = env_text(ACCOUNTS_ENV)
    if not raw:
        path = account_file or env_text(ACCOUNT_FILE_ENV)
        if not path and Path(DEFAULT_ACCOUNT_FILE).exists():
            path = DEFAULT_ACCOUNT_FILE
        if path:
            try:
                raw = Path(path).read_text(encoding="utf-8")
            except OSError as error:
                raise ConfigError("cannot read NEWAPI account file: %s" % error) from error
    accounts = parse_accounts(raw)
    if not accounts:
        base = env_text(BASE_URL_ENV)
        token = normalize_token(env_text(ACCESS_TOKEN_ENV))
        if base and token:
            accounts = [
                Account(
                    name="",
                    base_url=normalize_base_url(base),
                    access_token=token,
                    user_id=env_text(USER_ID_ENV),
                )
            ]
    deduped: List[Account] = []
    seen = set()
    for account in accounts:
        if account.fingerprint in seen:
            continue
        seen.add(account.fingerprint)
        deduped.append(account)
    if not deduped:
        raise ConfigError(
            "NEWAPI_ACCOUNTS, NEWAPI_ACCOUNT_FILE, or NEWAPI_BASE_URL + NEWAPI_ACCESS_TOKEN is not configured"
        )
    return deduped


def parse_only(value: str, total: int) -> set[int]:
    if not value.strip():
        return set(range(1, total + 1))
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as error:
                raise ConfigError("invalid --only range: %s" % part) from error
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            try:
                selected.add(int(part))
            except ValueError as error:
                raise ConfigError("invalid --only item: %s" % part) from error
    if not selected or min(selected) < 1 or max(selected) > total:
        raise ConfigError("--only contains an account outside 1..%d" % total)
    return selected


def response_data(payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def payload_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for source in (payload, payload.get("data")):
        if isinstance(source, dict):
            for key in ("code", "reason", "error"):
                value = source.get(key)
                if isinstance(value, dict):
                    value = value.get("code") or value.get("reason")
                if value is not None and str(value).strip():
                    return str(value).strip()
    return ""


def payload_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for source in (payload, payload.get("data")):
        if isinstance(source, dict):
            for key in ("message", "msg", "detail", "reason"):
                value = source.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
    return ""


def is_challenge_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        marker in lower
        for marker in (
            "turnstile",
            "captcha",
            "cf-challenge",
            "__cf_chl_",
            "just a moment",
            "attention required",
            "checking your browser",
            "cdn-cgi/challenge-platform",
            "验证码",
            "人机验证",
            "需要验证",
            "请完成验证",
            "安全验证",
            "驗證碼",
            "人機驗證",
            "需要驗證",
            "請完成驗證",
            "安全驗證",
        )
    )


def is_inactive_text(text: str) -> bool:
    lower = str(text or "").lower()
    has_context = any(
        marker in lower
        for marker in ("check-in", "checkin", "check in", "签到", "簽到")
    )
    has_inactive_marker = any(
        marker in lower
        for marker in (
            "not enabled",
            "disabled",
            "not available",
            "未开启",
            "未啟用",
            "未启用",
            "不可用",
        )
    )
    return has_context and has_inactive_marker


def is_pow_refusal(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        marker in lower
        for marker in (
            "pow",
            "proof of work",
            "工作量证明",
            "工作量證明",
        )
    )


def is_challenge_response(response: Any) -> bool:
    headers = getattr(response, "headers", {}) or {}
    if str(headers.get("cf-mitigated", "")).lower() == "challenge":
        return True
    status = int(getattr(response, "status_code", 0) or 0)
    server = str(headers.get("server", "")).lower()
    return status == 403 and "cloudflare" in server


def digest_matches(digest: bytes, difficulty: int) -> bool:
    if difficulty <= 0:
        return True
    full = difficulty // 8
    if full > len(digest):
        return False
    if any(byte != 0 for byte in digest[:full]):
        return False
    remainder = difficulty % 8
    if not remainder:
        return True
    if full >= len(digest):
        return False
    mask = (0xFF << (8 - remainder)) & 0xFF
    return (digest[full] & mask) == 0


def parse_challenge(payload: Any) -> Optional[PowChallenge]:
    data = response_data(payload)
    if not isinstance(data, dict):
        return None
    challenge_id = str(data.get("challenge_id") or "").strip()
    prefix = data.get("prefix") if isinstance(data.get("prefix"), str) else ""
    difficulty = parse_decimal(data.get("difficulty"))
    if not challenge_id or not prefix or difficulty is None:
        return None
    if difficulty < 0 or difficulty > 256:
        return None
    expires = parse_decimal(data.get("expires_at"))
    expires_at = float(expires) if expires is not None and expires > 0 else 0.0
    if expires_at > 1e12:
        expires_at /= 1000.0
    return PowChallenge(
        challenge_id=challenge_id,
        prefix=prefix,
        difficulty=int(difficulty),
        expires_at=expires_at,
    )


def solve_challenge(
    challenge: PowChallenge,
    budget_seconds: float = DEFAULT_POW_BUDGET,
) -> str:
    effective_budget = max(1.0, budget_seconds)
    if challenge.expires_at > 0:
        remaining = challenge.expires_at - time.time() - 3.0
        effective_budget = min(effective_budget, max(remaining, 3.0))
    deadline = time.monotonic() + effective_budget
    prefix = challenge.prefix.encode("utf-8")
    for counter in range(0x100000000):
        if (counter & 0x3FF) == 0 and time.monotonic() >= deadline:
            raise APIError("New API proof of work timed out", code="POW_TIMEOUT")
        nonce = "%08x" % counter
        if digest_matches(
            hashlib.sha256(prefix + nonce.encode("ascii")).digest(),
            challenge.difficulty,
        ):
            return nonce
    raise APIError("New API proof of work could not be solved", code="POW_FAILED")


class NewAPIClient:
    """HTTP client with an injectable session factory for offline tests."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
        pow_budget: float = DEFAULT_POW_BUDGET,
        proxy: str = "",
        session_factory: Any = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.timeout = max(1.0, float(timeout))
        self.wait_seconds = max(0.0, float(wait_seconds))
        self.pow_budget = max(1.0, float(pow_budget))
        self.proxy = str(proxy or "").strip()
        self.session_factory = session_factory or requests.Session
        self.sleeper = sleeper

    def _new_session(self) -> Any:
        session = self.session_factory()
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "NewAPI-Daily/1.0",
            }
        )
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        return session

    def _request(
        self,
        account: Account,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        session = self._new_session()
        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer %s" % account.access_token,
        }
        if account.user_id:
            headers["New-Api-User"] = account.user_id
        if body is not None:
            headers["Content-Type"] = "application/json"
        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            "params": query,
            "timeout": self.timeout,
            "allow_redirects": False,
        }
        if body is not None:
            request_kwargs["json"] = body
        try:
            response = session.request(
                method,
                account.base_url + path,
                **request_kwargs,
            )
        except requests.RequestException as error:
            raise APIError(
                "New API network request failed: %s"
                % sanitize_message(error, account)
            ) from error
        finally:
            session.close()

        status = int(getattr(response, "status_code", 0) or 0)
        text = getattr(response, "text", "") or ""
        if is_challenge_response(response):
            raise ManualRequired(
                "CAPTCHA",
                "New API requires a Cloudflare/Turnstile challenge",
            )
        if 300 <= status < 400:
            raise APIError(
                "New API returned a redirect (HTTP %d)" % status,
                status=status,
                code="REDIRECT",
            )
        try:
            payload = json.loads(text, parse_float=Decimal, parse_int=int)
        except (json.JSONDecodeError, TypeError) as error:
            if is_challenge_text(text):
                raise ManualRequired(
                    "CAPTCHA",
                    "New API requires a Cloudflare/Turnstile challenge",
                ) from error
            raise APIError(
                "New API returned non-JSON data (HTTP %d)" % status,
                status=status,
                code="INVALID_JSON",
            ) from error
        if not isinstance(payload, dict):
            raise APIError(
                "New API JSON top level is not an object (HTTP %d)" % status,
                status=status,
                code="INVALID_RESPONSE",
            )
        if is_challenge_text(payload_message(payload)):
            raise ManualRequired(
                "CAPTCHA",
                "New API requires a Cloudflare/Turnstile challenge",
            )
        return status, payload

    def status(self, account: Account) -> Tuple[CheckinStatus, int]:
        status, payload = self._request(account, "GET", CHECKIN_PATH)
        if status == 401:
            raise SessionExpired("New API login expired")
        message = payload_message(payload)
        if payload.get("success") is False:
            if is_challenge_text(message):
                raise ManualRequired("CAPTCHA", message or "captcha required")
            if is_inactive_text(message):
                return CheckinStatus(enabled=False, checked_in_today=False), status
        if status == 403:
            raise SessionExpired("New API login expired")
        if not 200 <= status < 300:
            raise APIError(
                "New API check-in status failed (HTTP %d): %s"
                % (status, sanitize_message(message, account)),
                status=status,
                code=payload_code(payload),
            )
        if payload.get("success") is False:
            raise APIError(
                "New API check-in status failed: %s" % sanitize_message(message, account),
                status=status,
                code=payload_code(payload),
            )
        data = response_data(payload)
        if not isinstance(data, dict):
            raise APIError(
                "New API status data is not an object",
                status=status,
                code="INVALID_RESPONSE",
            )
        stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
        enabled = data.get("enabled")
        checked = stats.get("checked_in_today", data.get("checked_in_today"))
        if not isinstance(enabled, bool) or not isinstance(checked, bool):
            raise APIError(
                "New API status lacks enabled/checked_in_today booleans",
                status=status,
                code="INVALID_RESPONSE",
            )
        records = stats.get("records") if isinstance(stats.get("records"), list) else []
        reward = parse_decimal(data.get("reward_amount"))
        if reward is None and records and isinstance(records[0], dict):
            reward = parse_decimal(records[0].get("quota_awarded"))
        return (
            CheckinStatus(
                enabled=enabled,
                checked_in_today=checked,
                reward_amount=reward,
                total_count=parse_decimal(stats.get("total_checkins") or stats.get("checkin_count")),
                total_amount=parse_decimal(stats.get("total_quota")),
            ),
            status,
        )

    def pow_challenge(self, account: Account) -> Optional[PowChallenge]:
        status, payload = self._request(
            account,
            "GET",
            POW_PATH,
            query={"action": "checkin"},
        )
        if status in (404, 405):
            return None
        if status in (401, 403):
            raise SessionExpired("New API login expired while reading PoW")
        if not 200 <= status < 300:
            raise APIError(
                "New API PoW challenge failed (HTTP %d): %s"
                % (status, sanitize_message(payload_message(payload), account)),
                status=status,
                code=payload_code(payload),
            )
        if payload.get("success") is False:
            message = payload_message(payload)
            if is_challenge_text(message):
                raise ManualRequired("CAPTCHA", message or "captcha required")
            raise APIError(
                "New API PoW challenge failed: %s" % sanitize_message(message, account),
                status=status,
                code=payload_code(payload),
            )
        return parse_challenge(payload)

    def claim(self, account: Account, challenge: Optional[PowChallenge]) -> Tuple[int, Any, bool]:
        query = None
        if challenge is not None:
            query = {
                "pow_challenge": challenge.challenge_id,
                "pow_nonce": solve_challenge(challenge, self.pow_budget),
            }
        status, payload = self._request(
            account,
            "POST",
            CHECKIN_PATH,
            query=query,
        )
        return status, payload, challenge is not None


def run_account(
    index: int,
    account: Account,
    client: NewAPIClient,
    query_only: bool = False,
) -> RunResult:
    label = account.label
    try:
        before, before_status = client.status(account)
        if not before.enabled:
            return RunResult(
                index=index,
                label=label,
                status="INACTIVE",
                message="站点当前没有开启每日签到活动",
                http_status=before_status,
                reward_amount=before.reward_amount,
                total_count=before.total_count,
                total_amount=before.total_amount,
            )
        if query_only:
            return RunResult(
                index=index,
                label=label,
                status="QUERY",
                message="查询完成；未发送签到请求",
                http_status=before_status,
                reward_amount=before.reward_amount,
                total_count=before.total_count,
                total_amount=before.total_amount,
            )
        if before.checked_in_today:
            return RunResult(
                index=index,
                label=label,
                status="ALREADY",
                message="今日已签到（服务端状态确认）",
                http_status=before_status,
                reward_amount=before.reward_amount,
                total_count=before.total_count,
                total_amount=before.total_amount,
            )

        challenge = client.pow_challenge(account)
        claim_status, payload, pow_used = client.claim(account, challenge)
        if (
            challenge is not None
            and (not 200 <= claim_status < 300 or payload.get("success") is False)
            and is_pow_refusal(payload_message(payload))
        ):
            refreshed = client.pow_challenge(account)
            if refreshed is not None:
                claim_status, payload, pow_used = client.claim(account, refreshed)
        if claim_status in (401, 403):
            raise SessionExpired("New API login expired while claiming")
        if not 200 <= claim_status < 300:
            message = payload_message(payload)
            if is_challenge_text(message):
                return RunResult(
                    index=index,
                    label=label,
                    status="MANUAL_REQUIRED",
                    message="签到需要 Cloudflare/Turnstile 验证，请手动完成",
                    http_status=claim_status,
                    pow_used=pow_used,
                )
            return RunResult(
                index=index,
                label=label,
                status="API_ERROR",
                message=sanitize_message(
                    message or "签到失败（HTTP %d）" % claim_status,
                    account,
                ),
                http_status=claim_status,
                pow_used=pow_used,
            )
        if payload.get("success") is False:
            message = payload_message(payload)
            if is_challenge_text(message):
                return RunResult(
                    index=index,
                    label=label,
                    status="MANUAL_REQUIRED",
                    message="签到需要 Cloudflare/Turnstile 验证，请手动完成",
                    http_status=claim_status,
                    pow_used=pow_used,
                )
            if "already" in message.lower() or "已签到" in message:
                after, after_status = client.status(account)
                if after.checked_in_today:
                    return RunResult(
                        index=index,
                        label=label,
                        status="ALREADY",
                        message="今日已签到（重复领取回读确认）",
                        http_status=after_status,
                        reward_amount=after.reward_amount,
                        total_count=after.total_count,
                        total_amount=after.total_amount,
                        pow_used=pow_used,
                    )
            if "not enabled" in message.lower() or "未开启" in message:
                return RunResult(
                    index=index,
                    label=label,
                    status="INACTIVE",
                    message="站点当前没有开启每日签到活动",
                    http_status=claim_status,
                    pow_used=pow_used,
                )
            return RunResult(
                index=index,
                label=label,
                status="API_ERROR",
                message=sanitize_message(message or "签到被服务端拒绝", account),
                http_status=claim_status,
                pow_used=pow_used,
            )

        data = response_data(payload)
        if not isinstance(data, dict):
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="签到响应缺少对象 data",
                http_status=claim_status,
                pow_used=pow_used,
            )
        awarded = parse_decimal(data.get("quota_awarded"))
        if awarded is None:
            awarded = parse_decimal(data.get("reward"))
        if awarded is None or awarded < 0:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="签到响应缺少有效的 quota_awarded",
                http_status=claim_status,
                pow_used=pow_used,
            )

        if client.wait_seconds:
            client.sleeper(client.wait_seconds)
        try:
            after, after_status = client.status(account)
        except NewAPIError as error:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="签到响应完整，但状态回读失败：%s"
                % sanitize_message(error, account),
                http_status=claim_status,
                reward_amount=awarded,
                pow_used=pow_used,
            )
        if not after.checked_in_today:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="签到响应成功，但服务端状态仍显示今日未签到",
                http_status=after_status,
                reward_amount=awarded,
                pow_used=pow_used,
            )
        return RunResult(
            index=index,
            label=label,
            status="CLAIMED",
            message="签到成功，服务端已回读今日状态和 quota_awarded",
            http_status=after_status,
            reward_amount=awarded,
            total_count=after.total_count,
            total_amount=after.total_amount,
            pow_used=pow_used,
        )
    except ManualRequired as error:
        return RunResult(
            index=index,
            label=label,
            status="MANUAL_REQUIRED",
            message="需要人工处理：%s" % sanitize_message(error, account),
        )
    except SessionExpired as error:
        return RunResult(
            index=index,
            label=label,
            status="AUTH_EXPIRED",
            message=sanitize_message(error, account),
        )
    except ConfigError as error:
        return RunResult(
            index=index,
            label=label,
            status="CONFIG_ERROR",
            message=sanitize_message(error, account),
        )
    except APIError as error:
        return RunResult(
            index=index,
            label=label,
            status="UNCONFIRMED"
            if error.code in {"INVALID_RESPONSE", "INVALID_JSON"}
            else "API_ERROR",
            message=sanitize_message(error, account),
            http_status=error.status,
        )


def build_summary(results: Sequence[RunResult]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "type": "SUMMARY",
        "provider": PROVIDER,
        "ok": bool(results) and all(result.ok for result in results),
        "accounts": len(results),
        "claimed": counts.get("CLAIMED", 0),
        "already": counts.get("ALREADY", 0),
        "query": counts.get("QUERY", 0),
        "inactive": counts.get("INACTIVE", 0),
        "manual_required": counts.get("MANUAL_REQUIRED", 0),
        "failed": sum(1 for result in results if not result.ok),
        "status_counts": counts,
    }


def build_report(results: Sequence[RunResult], summary: Dict[str, Any]) -> str:
    lines = [
        "NewAPI Daily",
        "账号：%d；已领取：%d；今日已签：%d；失败：%d"
        % (len(results), summary["claimed"], summary["already"], summary["failed"]),
    ]
    for result in results:
        lines.append(
            "%s 账号%d %s：%s"
            % ("✅" if result.ok else "❌", result.index, result.label, result.message)
        )
    return "\n".join(lines)


def _post_notification(url: str, payload: Dict[str, Any]) -> None:
    requests.post(url, json=payload, timeout=10)


def notify_all(title: str, content: str) -> None:
    pushplus = env_text("PUSHPLUS_TOKEN")
    if pushplus:
        try:
            _post_notification(
                "https://www.pushplus.plus/send",
                {"token": pushplus, "title": title, "content": content, "template": "markdown"},
            )
        except requests.RequestException:
            pass
    wecom = env_text("WECOM_WEBHOOK")
    if wecom:
        try:
            _post_notification(wecom, {"msgtype": "markdown", "markdown": {"content": content}})
        except requests.RequestException:
            pass
    dingtalk = env_text("DINGTALK_WEBHOOK")
    if dingtalk:
        try:
            _post_notification(
                dingtalk,
                {"msgtype": "markdown", "markdown": {"title": title, "text": content}},
            )
        except requests.RequestException:
            pass
    bark = env_text("BARK_URL")
    if bark:
        try:
            requests.get(bark, params={"title": title, "body": content}, timeout=10)
        except requests.RequestException:
            pass
    generic = env_text("GENERIC_WEBHOOK_URL")
    if generic:
        try:
            _post_notification(generic, {"title": title, "content": content})
        except requests.RequestException:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="New API daily check-in")
    parser.add_argument("--query", "--status", action="store_true", dest="query", help="read status only")
    parser.add_argument("--only", default="", help="account indexes, e.g. 1,3-4")
    parser.add_argument("--accounts-file", default="", help="account file path")
    parser.add_argument("--wait-seconds", type=float, default=None, help="wait before status readback")
    parser.add_argument("--pow-budget", type=float, default=None, help="PoW solver budget seconds")
    parser.add_argument("--no-notify", action="store_true", help="disable notifications")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        accounts = load_accounts(args.accounts_file or None)
        selected = parse_only(args.only, len(accounts))
    except ConfigError as error:
        emit(
            {
                "type": "SUMMARY",
                "provider": PROVIDER,
                "ok": False,
                "accounts": 0,
                "error": sanitize_message(error),
            }
        )
        return 2

    wait_seconds = (
        DEFAULT_WAIT_SECONDS
        if args.wait_seconds is None
        else max(0.0, float(args.wait_seconds))
    )
    if args.wait_seconds is None and env_text(WAIT_ENV):
        try:
            wait_seconds = max(0.0, float(env_text(WAIT_ENV)))
        except ValueError:
            pass
    pow_budget = (
        DEFAULT_POW_BUDGET
        if args.pow_budget is None
        else max(1.0, float(args.pow_budget))
    )

    client = NewAPIClient(
        wait_seconds=wait_seconds,
        pow_budget=pow_budget,
        proxy=env_text(PROXY_ENV),
    )
    results: List[RunResult] = []
    for index, account in enumerate(accounts, 1):
        if index not in selected:
            continue
        result = run_account(index, account, client, query_only=args.query)
        results.append(result)
        emit(result.as_dict())

    summary = build_summary(results)
    emit(summary)
    if not args.no_notify:
        notify_all("NewAPI Daily", build_report(results, summary))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
