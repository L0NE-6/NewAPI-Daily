<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily

**New API 일일 체크인 · PoW 지원 · Cloudflare/Turnstile 명시적 수동 처리 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## 기능

New API 체크인 상태를 읽고, 사이트가 PoW를 제공하면 해결한 뒤 body 없는 POST를 보내고 다시 상태를 읽습니다. `success`, `quota_awarded`, 이후 `checked_in_today=true`가 모두 확인되어야 `CLAIMED`로 보고합니다.

## 설정

`NEWAPI_ACCOUNTS`는 `라벨|baseURL|accessToken|userId` 형식입니다. JSON 배열과 `NEWAPI_BASE_URL`/`NEWAPI_ACCESS_TOKEN` 단일 계정 변수도 지원합니다.

## 프로토콜

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

POST에는 body가 없습니다. PoW는 `pow_challenge`와 `pow_nonce`로 전송합니다. Cloudflare/Turnstile은 `MANUAL_REQUIRED`로 표시하며 성공으로 처리하지 않습니다.

서버가 PoW를 명시적으로 거부하면 새 문제를 받아 한 번만 재시도합니다. 체크인 비활성화를 뜻하는 업무 오류는 `INACTIVE`로 처리합니다.

## 실행

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='main|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
python newapi_daily.py --query
python newapi_daily.py --only 1,3-4
```

## 개인정보

Token, 계정 파일, 보고서, 로그, 자격 증명이 포함된 스크린샷을 커밋하지 마세요. 출력에서는 식별자, Token, 알림 비밀값을 가립니다.
