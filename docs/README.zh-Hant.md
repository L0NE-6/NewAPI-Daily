<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily

**New API 每日簽到 · PoW 支援 · Cloudflare/Turnstile 明確人工處理 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · **繁體中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)
> 版本：**v1.0.0**（2026-11-24）

</div>

## 功能

讀取 New API 今日簽到狀態，站點提供 PoW 時先求解，再提交無 body 的 POST，最後再次讀取狀態。只有 `success`、`quota_awarded` 與後續 `checked_in_today=true` 都成立時，才回報 `CLAIMED`。

## 設定

`NEWAPI_ACCOUNTS` 格式為 `備註|baseURL|accessToken|userId`。也支援 JSON 陣列與 `NEWAPI_BASE_URL`、`NEWAPI_ACCESS_TOKEN` 單帳號變數。

## 協議

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

POST 不帶 body；PoW 使用 `pow_challenge` 與 `pow_nonce`。Cloudflare/Turnstile 一律標記 `MANUAL_REQUIRED`，不會偽報成功。PoW 或狀態回讀不足時標記 `UNCONFIRMED`。

服務端明確拒絕 PoW（例如題目過期）時，腳本會重新取題並最多重試一次。站點以業務錯誤表示簽到未開啟時，按 `INACTIVE` 中性處理。

## 執行

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='主號|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
python newapi_daily.py --query
python newapi_daily.py --only 1,3-4
```

## 隱私

不要提交 Token、帳號檔案、報告、日誌或含憑證的截圖。腳本會遮蔽帳號標識、Token 與推送憑證。
