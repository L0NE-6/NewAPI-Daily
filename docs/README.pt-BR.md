<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily

**Check-in diário do New API · suporte a PoW · tratamento manual explícito de Cloudflare/Turnstile · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## O que faz

Lê o estado do check-in, resolve um desafio PoW quando o site oferece um, envia
o POST sem body e lê o estado novamente. Só informa `CLAIMED` quando `success`,
`quota_awarded` e `checked_in_today=true` na leitura posterior estão presentes.

## Configuração

Use `NEWAPI_ACCOUNTS` no formato `rótulo|baseURL|accessToken|userId`. Listas
JSON e as variáveis `NEWAPI_BASE_URL`/`NEWAPI_ACCESS_TOKEN` também funcionam.

## Protocolo

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

O POST não envia body. O PoW usa `pow_challenge` e `pow_nonce`. Desafios
Cloudflare/Turnstile resultam em `MANUAL_REQUIRED`, nunca em sucesso.
Se o servidor rejeitar explicitamente o PoW, o script solicita um novo desafio
e tenta mais uma vez. Um erro de negócio indicando check-in desativado é
tratado como `INACTIVE`.

## Execução

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='principal|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
python newapi_daily.py --query
python newapi_daily.py --only 1,3-4
```

## Privacidade

Não faça commit de tokens, arquivos de conta, relatórios, logs ou capturas com
credenciais. O script oculta identificadores, tokens e segredos de notificação.
