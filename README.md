<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧱 NewAPI Daily

**New API 每日签到 · PoW 支持 · Cloudflare/Turnstile 明确人工处理 · JSONL**

> 当前版本：**v1.0.0**（2026-11-24） · 由 L0NE-6 原创维护

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

🔐 Access Token · 🧮 PoW 求解 · 🎁 每日签到 · 👥 多账号隔离 · 🧾 JSONL · 📢 可选推送 · 🐧 青龙友好 · ☁️ GitHub Actions

<img src="https://img.shields.io/badge/Version-v1.0.0-2ea44f?style=for-the-badge&logo=github" />
<img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20%E9%9D%92%E9%BE%99-4EAA25?style=for-the-badge&logo=linux&logoColor=white" />
<img src="https://img.shields.io/badge/Deploy-%E9%9D%92%E9%BE%99%20%7C%20GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" />

</div>

---

<a id="usage-policy"></a>
## 🚫 使用边界

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。

禁止将本仓库、脚本、部署说明或 Release 包装成付费资源、内部版、独家版、会员权益、收费课程、代部署服务或包更新服务；禁止删除作者与版权信息后冒充原创。完整规则见 **[NOTICE.md](NOTICE.md)**。

---

## ✨ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **做什么** | 读取 New API 站点的今日签到状态，必要时求解 PoW，提交签到并再次回读状态。 |
| **输入** | 一个或多个站点根地址、`accessToken`，可选 `userId`。 |
| **输出** | 每账号一行 JSON，最后一行 `SUMMARY` JSON。 |
| **部署** | Windows / Linux / 青龙面板 / GitHub Actions。 |
| **依赖** | Python 3.9+；运行时依赖 `requests`。 |
| **成功判据** | POST 返回 `success` 和 `quota_awarded`，且再次 GET 确认 `checked_in_today=true`。 |

---

## 🧠 签到与 PoW

基础流程：

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

`POST` 不发送请求体。如果站点返回 PoW 题目，脚本会：

1. 读取 `challenge_id`、`prefix`、`difficulty`；
2. 计算 `sha256(prefix + nonce)`，寻找满足难度的 8 位十六进制 nonce；
3. 在 POST 查询参数中携带 `pow_challenge` 和 `pow_nonce`；
4. POST 后重新 GET，必须读到 `stats.checked_in_today=true`；
5. `quota_awarded` 必须是有效非负数字，否则报告 `UNCONFIRMED`。

如果服务端明确拒绝 PoW（例如题目过期），脚本会重新取题并最多重试一次。站点通过业务错误表示签到未开启时，脚本按 `INACTIVE` 中性处理。

如果站点要求 Cloudflare 或 Turnstile 验证，脚本报告 `MANUAL_REQUIRED`，不会把 HTML 验证页或 HTTP 200 当成签到成功。

---

## 🔑 账号格式

```text
主号|https://newapi.example|ACCESS_TOKEN|42
小号|https://newapi2.example|ACCESS_TOKEN_2|43
```

也支持 JSON：

```json
[
  {
    "name": "主号",
    "baseURL": "https://newapi.example",
    "accessToken": "ACCESS_TOKEN",
    "userId": "42"
  }
]
```

站点填写根地址或已有子路径，不要填写 `/api/user/checkin`。

---

## 🚀 青龙面板

1. 将 `newapi_daily.py` 上传到青龙脚本目录。
2. 在青龙环境变量中新增 `NEWAPI_ACCOUNTS`，或设置单账号变量。
3. 新建任务，命令使用 `task newapi_daily.py`。
4. 在青龙依赖管理中安装 `requests`，或执行 `pip3 install requests`。

建议每天运行一次，例如 `17 7 * * *`。

---

## ☁️ GitHub Actions

工作流位于 `.github/workflows/newapi.yml`：

- `push` 到 `main`：运行离线测试、编译检查和 Ruff；
- `schedule`：每天执行一次；
- `workflow_dispatch`：手动运行；
- 未配置 Secret 时跳过在线执行并输出 notice；
- JSONL 原始结果作为 artifact 保留。

Secret 可使用 `NEWAPI_ACCOUNTS`，或 `NEWAPI_BASE_URL` + `NEWAPI_ACCESS_TOKEN` + `NEWAPI_USER_ID`。

---

## 🔧 环境变量

| 变量 | 必填 | 说明 |
| :--- | :---: | :--- |
| `NEWAPI_ACCOUNTS` | 二选一 | 多账号，`备注\|baseURL\|accessToken\|userId` |
| `NEWAPI_ACCOUNT_FILE` | 可选 | 本地账号文件 |
| `NEWAPI_BASE_URL` | 可选 | 单账号站点地址 |
| `NEWAPI_ACCESS_TOKEN` | 可选 | 单账号 accessToken |
| `NEWAPI_USER_ID` | 可选 | 单账号 userId |
| `NEWAPI_PROXY` | 可选 | HTTP(S) 代理 |
| `NEWAPI_WAIT_SECONDS` | 可选 | 领取后状态回读等待秒数 |
| `PUSHPLUS_TOKEN` | 可选 | PushPlus |
| `BARK_URL` | 可选 | Bark |
| `WECOM_WEBHOOK` | 可选 | 企业微信机器人 |
| `DINGTALK_WEBHOOK` | 可选 | 钉钉机器人 |
| `GENERIC_WEBHOOK_URL` | 可选 | 通用 JSON webhook |

---

## ⌨️ 本地运行

```powershell
python -m pip install -r requirements.txt
$env:NEWAPI_ACCOUNTS = "主号|https://newapi.example|ACCESS_TOKEN|42"
python .\newapi_daily.py
python .\newapi_daily.py --query
python .\newapi_daily.py --only 1,3-4
python .\newapi_daily.py --pow-budget 60
python .\newapi_daily.py --no-notify
```

`--query` 只查询签到状态，不读取 PoW、不提交签到。

---

## ✅ 结果状态

| 状态 | 含义 | 是否成功 |
| :--- | :--- | :---: |
| `CLAIMED` | POST 成功且回读确认今日已签 | ✅ |
| `ALREADY` | 服务端确认今日已经领取 | ✅ |
| `QUERY` | 查询模式，未提交签到 | ✅ |
| `INACTIVE` | 站点未开启签到 | ✅ |
| `MANUAL_REQUIRED` | Cloudflare/Turnstile 或人工验证 | ❌ |
| `AUTH_EXPIRED` | Access Token 失效 | ❌ |
| `UNCONFIRMED` | PoW/领取字段或状态回读不足 | ❌ |
| `API_ERROR` / `CONFIG_ERROR` | HTTP、JSON、PoW 或配置错误 | ❌ |

---

## 🧪 测试与质量检查

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
python -m ruff check .
```

测试使用 fake session，不访问真实 New API 站点，不需要真实 Token。

---

## 🔒 隐私说明

- 仓库不包含账号、Access Token、userId 或推送凭据。
- 凭据只通过环境变量、青龙变量或 GitHub Secrets 注入。
- 输出会脱敏账号标识、Token 和推送凭据。
- `.gitignore` 已排除本地账号文件、报告、缓存和日志。

---

## ☕ 支持与投喂

脚本完全免费。如果它确实帮你省了时间，欢迎自愿赞赏；不影响任何功能，也不影响 Issue 响应。

<p align="center">
  <img src="assets/donate-wechat.png" width="260" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="260" alt="支付宝收款码" />
</p>
<p align="center"><sub>💚 微信支付（左） &nbsp;|&nbsp; 💙 支付宝（右）</sub></p>

---

## ⚠️ 免责声明

本项目用于个人学习和合法的个人自动化。New API 各站点的活动规则、接口、奖励和账号资格由站点决定；使用前请确认对应服务条款，并自行承担账号、网络和活动变化带来的风险。
