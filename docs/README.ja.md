<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily

**New API 毎日チェックイン · PoW 対応 · Cloudflare/Turnstile を明示的に手動処理 · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · **日本語** · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)
> バージョン：**v1.0.0**（2026-11-24）

</div>

## 機能

New API のチェックイン状態を読み取り、PoW があれば解いてから空の POST を送り、再度状態を読み取ります。`success`、`quota_awarded`、および再読取の `checked_in_today=true` が揃った場合だけ `CLAIMED` と報告します。

## 設定

`NEWAPI_ACCOUNTS` は `ラベル|baseURL|accessToken|userId` 形式です。JSON 配列と `NEWAPI_BASE_URL` / `NEWAPI_ACCESS_TOKEN` の単一アカウント変数も利用できます。

## プロトコル

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

POST に body はありません。PoW は `pow_challenge` と `pow_nonce` で送ります。Cloudflare/Turnstile は `MANUAL_REQUIRED` とし、成功扱いしません。

サーバーが PoW を明示的に拒否した場合は、新しい問題を取得して一度だけ再試行します。チェックイン無効を示す業務エラーは `INACTIVE` として扱います。

## 実行

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='main|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
python newapi_daily.py --query
python newapi_daily.py --only 1,3-4
```

## プライバシー

Token、アカウントファイル、レポート、ログ、認証情報を含む画像をコミットしないでください。出力では識別子、Token、通知用の秘密値を伏せます。
