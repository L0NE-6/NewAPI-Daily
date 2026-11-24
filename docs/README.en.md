<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily
[简体中文](../README.md) · **English** · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)
> Version: **v1.0.0** (2026-11-24)

**New API daily check-in · PoW support · explicit Cloudflare/Turnstile manual handling · JSONL**


</div>

## What it does

Reads the check-in state, solves a PoW challenge when the site provides one,
submits the empty-body POST, and reads the status again. A claim is reported as
`CLAIMED` only when `success` and `quota_awarded` are present and the later
status confirms `checked_in_today=true`.

## Configuration

Use `NEWAPI_ACCOUNTS` with `label|baseURL|accessToken|userId`. JSON lists and
single-account `NEWAPI_BASE_URL`/`NEWAPI_ACCESS_TOKEN` variables are supported.
The site URL should be the site root, not `/api/user/checkin`.

## Protocol

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

The POST has no body. PoW values are sent as `pow_challenge` and `pow_nonce`.
If the server explicitly rejects a PoW answer, the script requests a fresh
challenge and retries once. A business response that says check-in is not
enabled is treated as `INACTIVE`.
Cloudflare or Turnstile challenges are reported as `MANUAL_REQUIRED`, never as
success. Missing PoW fields, missing `quota_awarded`, or an unconfirmed status
readback are `UNCONFIRMED`.

## Run locally

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='main|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
python newapi_daily.py --query
python newapi_daily.py --only 1,3-4
```

## Privacy

Do not commit tokens, account files, reports, logs, or screenshots containing
credentials. The script redacts identifiers, tokens, and notification secrets.

## Test

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
python -m ruff check .
```

All tests use fake HTTP sessions and do not call the live service.
