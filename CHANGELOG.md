# Changelog

## v1.0.0 - 2026-11-24

- Added the standalone New API daily check-in script.
- Added multi-account access-token account forms and per-account isolation.
- Added proof-of-work challenge parsing, bounded nonce solving, empty-body
  claim submission, one fresh-challenge retry after an explicit PoW refusal,
  and strict `checked_in_today`/`quota_awarded` readback.
- Added neutral already-claimed and inactive-site handling, plus explicit
  manual, authentication, malformed-response, and unconfirmed outcomes.
- Added context-aware inactive detection, email redaction, normalized host
  fingerprints, and escaped-JSON challenge handling.
- Added optional notifications, offline tests, GitHub Actions, MIT licensing,
  usage policy, third-party notices, six-language documentation, and QR assets.
