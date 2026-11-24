<div align="center">

<sub><strong>L0NE-6 · NEWAPI SIGNAL</strong></sub>

# NewAPI Daily

**New API 每日签到 · PoW 支持 · 人工验证显式分类 · JSONL**

> 当前版本：**v1.0.0**（2026-11-24） · 空 body 提交，PoW 有界求解，签到后必须回读 checked_in_today

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

<img src="https://img.shields.io/badge/Features-PoW%20Check-in-6F42C1?style=for-the-badge" alt="Features" />
<a href="https://github.com/L0NE-6/NewAPI-Daily/releases"><img src="https://img.shields.io/github/v/release/L0NE-6/NewAPI-Daily?style=for-the-badge&label=Release&color=2ea44f&logo=github" alt="Release" /></a>
<a href="https://github.com/L0NE-6/NewAPI-Daily/stargazers"><img src="https://img.shields.io/github/stars/L0NE-6/NewAPI-Daily?style=for-the-badge&label=Stars&color=FFC75F&logo=github" alt="Stars" /></a>
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Qinglong-4EAA25?style=for-the-badge&logo=linux&logoColor=white" alt="Platform" />
<img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" alt="License" />

🔐 Access Token · 🧮 PoW · 🎁 每日签到 · 👥 多账号 · 🧾 JSONL · 🐧 青龙 · ☁️ Actions

[⚡ 30 秒速览](#quick-look) · [🔁 协议与回读](#protocol) · [🔐 凭据](#credentials) · [🐧 青龙](#qinglong) · [☁️ Actions](#actions) · [⌨️ CLI](#cli-json) · [✅ 成功判据](#success) · [✦ 星轨](#star-trail)

</div>

---

<a id="usage-policy"></a>
## 🚫 使用边界与禁止倒卖

> [!IMPORTANT]
> **官方版本永久免费。** 未经作者书面许可，禁止倒卖、付费包装、搬运引流、冒充作者，或使用作者身份与二维码制造官方授权假象。

本仓库、脚本、部署说明和 Release 下载保持免费公开。禁止将本项目或其轻度改名版本包装为付费资源、内部版、独家版、会员权益、收费课程、代部署服务或包更新服务；禁止搬运到其他账号、群组、频道、网盘、电商平台或付费社群进行涨粉、截流、倒卖和引流；禁止删除作者与版权信息后冒充原创。

完整规则见 [NOTICE.md](NOTICE.md)。第三方以“下载费 / 激活费 / 内部版 / 代部署 / 会员门槛”等名义收费，均与作者无关，请停止付款并保留证据。

---

<a id="quick-look"></a>
## ⚡ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **做什么** | 读取 New API 签到状态，必要时求解 PoW，提交签到并再次回读。 |
| **输入** | 一个或多个站点根地址、`accessToken`，可选 `userId`。 |
| **协议** | `GET /api/user/checkin` → PoW challenge → 空 body `POST` → 再读状态。 |
| **输出** | 每账号一条 JSON，最后一行 `SUMMARY` JSON。 |
| **成功判据** | POST 有 `success` / `quota_awarded`，回读 `stats.checked_in_today=true`。 |
| **人工验证** | Cloudflare / Turnstile 明确返回 `MANUAL_REQUIRED`。 |

---

## 🧭 这是什么 / 覆盖范围

New API 脚本面向自填站点根地址，不绑定某一个公共域名。它先读取签到状态，站点要求 PoW 时读取 challenge、在本地求解并提交 `pow_challenge` / `pow_nonce`，最后重新读取状态。

### 覆盖范围

- 多站点、多账号 `备注|baseURL|accessToken|userId`。
- `accessToken` + `New-Api-User` 请求头。
- PoW challenge 解析、有界 nonce 求解和一次新鲜 challenge 重试。
- `checked_in_today`、`quota_awarded` 和签到统计字段回读。
- Cloudflare / Turnstile 人工验证、站点未开启、鉴权失效、未确认状态明确分类。
- JSONL、Actions artifact 和可选通知。

---

<a id="protocol"></a>
## 🔁 协议与回读流程

### 请求链

```http
GET  /api/user/checkin
GET  /api/user/pow/challenge?action=checkin
POST /api/user/checkin
GET  /api/user/checkin
Authorization: Bearer <NEWAPI_ACCESS_TOKEN>
New-Api-User: <NEWAPI_USER_ID>
```

签到 POST 不发送请求体。PoW 题目包含 `challenge_id`、`prefix`、`difficulty` 时，脚本计算 `sha256(prefix + nonce)`，寻找满足难度的 8 位十六进制 nonce，并在查询参数中携带 `pow_challenge`、`pow_nonce`。

| 字段 | 说明 |
| :--- | :--- |
| `stats.checked_in_today` | 今日签到状态。 |
| `quota_awarded` | 本次奖励额度，必须为有效非负数字。 |
| `reward_amount` / `total_count` / `total_amount` | 状态统计。 |
| `pow_used` | 本次是否使用 PoW。 |
| `enabled` | 站点是否开放签到。 |

服务端明确拒绝过期 PoW 时重新取题并最多重试一次。Cloudflare、Turnstile 或人工验证返回 `MANUAL_REQUIRED`。

---

<a id="credentials"></a>
## 🔐 凭据与环境变量

### 账号格式

```text
主号|https://newapi.example|ACCESS_TOKEN|42
小号|https://newapi2.example|ACCESS_TOKEN_2|43
```

也支持 JSON，字段为 `name`、`baseURL`、`accessToken`、`userId`。站点填根地址或已有子路径，不要填写 `/api/user/checkin`。

| 变量 | 必填 | 说明 |
| :--- | :---: | :--- |
| `NEWAPI_ACCOUNTS` | 二选一 | 多账号列表。 |
| `NEWAPI_ACCOUNT_FILE` | 否 | 本地账号文件。 |
| `NEWAPI_BASE_URL` | 二选一 | 单账号站点地址。 |
| `NEWAPI_ACCESS_TOKEN` | 二选一 | 单账号 accessToken。 |
| `NEWAPI_USER_ID` | 否 | 单账号 userId。 |
| `NEWAPI_PROXY` | 否 | HTTP(S) 代理。 |
| `NEWAPI_WAIT_SECONDS` | 否 | 状态回读等待秒数。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 否 | 推送。 |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` | 否 | 群机器人。 |
| `GENERIC_WEBHOOK_URL` | 否 | 通用 JSON webhook。 |

---

## 💻 本地快速开始

### PowerShell

```powershell
python -m pip install -r requirements.txt
$env:NEWAPI_ACCOUNTS = "主号|https://newapi.example|ACCESS_TOKEN|42"
python .\newapi_daily.py
```

### Bash

```bash
python -m pip install -r requirements.txt
export NEWAPI_ACCOUNTS='主号|https://newapi.example|ACCESS_TOKEN|42'
python newapi_daily.py
```

常用参数：`--query`、`--only 1,3-4`、`--accounts-file newapi_accounts.txt`、`--pow-budget 60`、`--wait-seconds 0.5`、`--no-notify`。

---

<a id="qinglong"></a>
## 🐧 青龙

1. 在青龙依赖管理中安装 `requests`，或执行 `pip3 install -r requirements.txt`。
2. 上传 `newapi_daily.py` 到脚本目录。
3. 在环境变量中配置 `NEWAPI_ACCOUNTS`，或 `NEWAPI_BASE_URL` + `NEWAPI_ACCESS_TOKEN` + `NEWAPI_USER_ID`。
4. 新建定时任务，命令使用 `task newapi_daily.py`，不要直接写裸 `python`。
5. 建议北京时间：`17 7 * * *`。青龙按面板本地时间执行。

```bash
pip3 install -r requirements.txt
task newapi_daily.py
```

---

<a id="actions"></a>
## ☁️ GitHub Actions、Secrets 与定时

工作流：`.github/workflows/newapi.yml`。

| 事件 | 行为 |
| :--- | :--- |
| `push` 到 `main` | pytest、编译检查、Ruff。 |
| `schedule` | 先测试，再执行签到并上传 JSONL artifact。 |
| `workflow_dispatch` | 手动执行。 |
| 未配置 Secret | 输出 notice 并跳过在线执行。 |

### Secrets

| Secret | 说明 |
| :--- | :--- |
| `NEWAPI_ACCOUNTS` | 多账号列表。 |
| `NEWAPI_BASE_URL` | 单账号站点。 |
| `NEWAPI_ACCESS_TOKEN` | 单账号 accessToken。 |
| `NEWAPI_USER_ID` | 单账号 userId。 |
| `NEWAPI_PROXY` | 可选代理。 |
| `NEWAPI_WAIT_SECONDS` | 状态回读等待秒数。 |
| `PUSHPLUS_TOKEN` / `BARK_URL` | 推送。 |
| `WECOM_WEBHOOK` / `DINGTALK_WEBHOOK` | 群机器人。 |
| `GENERIC_WEBHOOK_URL` | 通用 JSON webhook。 |

内置 cron 为 `17 7 * * *`。GitHub cron 使用 UTC，因此对应北京时间约 15:17；青龙示例使用本地时间 07:17。

---

<a id="cli-json"></a>
## ⌨️ CLI 与 JSON 输出

```powershell
python .\newapi_daily.py
python .\newapi_daily.py --query
python .\newapi_daily.py --only 1,3-4
python .\newapi_daily.py --pow-budget 60
python .\newapi_daily.py --no-notify
```

账号 JSON 示例：

```json
{"type":"account","provider":"newapi","index":1,"label":"主号","status":"CLAIMED","ok":true,"message":"服务端确认签到","http_status":200,"reward_amount":"10","total_count":"1","total_amount":"10","pow_used":true,"details":[]}
```

| 字段 | 说明 |
| :--- | :--- |
| `status` / `ok` | 结果状态与是否成功。 |
| `reward_amount` | 本次签到奖励。 |
| `total_count` / `total_amount` | 签到统计。 |
| `pow_used` | 是否使用 PoW。 |
| `details` | 非敏感补充信息。 |

---

<a id="result-codes"></a>
## 🧾 结果码

| 结果码 | 成功 | 含义 |
| :--- | :---: | :--- |
| `CLAIMED` | 是 | POST 成功且回读确认今日已签。 |
| `ALREADY` | 是 | 服务端确认今日已经领取。 |
| `QUERY` | 是 | 查询模式，未提交签到。 |
| `INACTIVE` | 是 | 站点未开启签到。 |
| `MANUAL_REQUIRED` | 否 | Cloudflare、Turnstile 或人工验证。 |
| `AUTH_EXPIRED` | 否 | Access Token 失效。 |
| `UNCONFIRMED` | 否 | PoW、奖励字段或状态回读不足。 |
| `API_ERROR` | 否 | HTTP、JSON、PoW 或业务错误。 |
| `CONFIG_ERROR` | 否 | 站点、账号或参数配置错误。 |

---

<a id="success"></a>
## ✅ 成功判据

| 场景 | 必须满足 |
| :--- | :--- |
| 本次签到 | POST 返回 `success` 与有效 `quota_awarded`，且再次 GET 的 `stats.checked_in_today=true`。 |
| 今日已签到 | 查询阶段已返回 `checked_in_today=true`。 |
| 站点未开启 | 业务错误明确表示签到未启用，结果 `INACTIVE`。 |
| 人工验证 | Cloudflare / Turnstile 出现时返回 `MANUAL_REQUIRED`。 |
| 未确认 | PoW 失败、奖励字段缺失或状态未翻转时失败。 |

---

## 🧪 测试与静态检查

```bash
python -m pytest -q
python -m compileall -q .
python -m ruff check .
```

离线测试覆盖账号解析、HTTP 站点限制、主机规范化、PoW 成功、无 PoW 路径、奖励缺失、Cloudflare/Turnstile、中文验证、站点未开启、PoW 拒绝后重试、已签到短路和求解预算。

---

## 🧱 设计原则

- **PoW 有界**：预算、截止时间和 nonce 范围明确。
- **空 body 提交**：不注入非协议字段。
- **人工验证显式化**：Cloudflare / Turnstile 不伪装成普通失败。
- **回读定成功**：POST 回执必须由再次 GET 确认。
- **多站点隔离**：不同 baseURL 与 userId 独立处理。

---

## 🔒 隐私

仓库不包含账号、Access Token、userId、站点密码、日志或真实响应。`newapi_accounts.txt`、`newapi-report.json`、`newapi-report.jsonl`、`auth.json`、Cookie 和缓存已由 `.gitignore` 排除。

---

## 📁 目录结构

```text
NewAPI-Daily/
├── .github/workflows/newapi.yml
├── assets/
│   ├── donate-alipay.jpg
│   └── donate-wechat.png
├── docs/
│   ├── README.en.md
│   ├── README.zh-Hant.md
│   ├── README.ja.md
│   ├── README.ko.md
│   └── README.pt-BR.md
├── tests/test_newapi_daily.py
├── CHANGELOG.md
├── LICENSE
├── NOTICE.md
├── THIRD_PARTY_NOTICES.md
├── newapi_daily.py
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## 📦 版本与发布

- 当前清单版本：`v1.0.0`，日期 `2026-11-24`。
- 脚本版本与 `newapi_daily.py` 内的 `VERSION` 保持一致。
- 更新记录见 [CHANGELOG.md](CHANGELOG.md)，下载入口见 [Releases](https://github.com/L0NE-6/NewAPI-Daily/releases)。
- Release 徽标由 GitHub 实时生成；如果页面尚未创建对应 Release，以 `CHANGELOG.md` 和仓库提交为准。

---

## ⚠️ 免责声明

本项目用于个人学习与个人自动化。New API 站点 的活动规则、接口、奖励、风控策略和账号资格由服务方决定。使用前请确认对应服务条款，并自行承担接口变化、账号限制和网络环境带来的风险。

---

## ☕ 支持与投喂

脚本完全免费，赞赏纯自愿，不影响任何功能，也不影响 Issue 响应。

<p align="center">
  <img src="assets/donate-wechat.png" width="260" alt="微信赞赏码" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/donate-alipay.jpg" width="260" alt="支付宝收款码" />
</p>
<p align="center"><sub>💚 微信支付（左） &nbsp;|&nbsp; 💙 支付宝（右，支持信用卡 / 花呗）</sub></p>

> 收款码仅用于向作者自愿赞赏。任何第三方以代下载、代部署、内部资源或会员群为由收费，均与作者无关。

---

## 💬 反馈与贡献

- 提交 [Issue](https://github.com/L0NE-6/NewAPI-Daily/issues) 时附运行日志、脱敏后的错误字段和复现步骤。
- 发起 [Pull Request](https://github.com/L0NE-6/NewAPI-Daily/pulls) 时保持单文件运行、离线测试和凭据脱敏约束。
- 不要在任何 Issue、PR、截图或日志中粘贴真实 Token、Cookie、密码、UID、手机号或邮箱。

---

<a id="star-trail"></a>
## ✦ Star History / 星轨

<a href="https://star-history.com/#L0NE-6/NewAPI-Daily&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=L0NE-6/NewAPI-Daily&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=L0NE-6/NewAPI-Daily&type=Date" />
    <img alt="NewAPI-Daily Star History" src="https://api.star-history.com/svg?repos=L0NE-6/NewAPI-Daily&type=Date" />
  </picture>
</a>

<div align="center">
  <sub>L0NE-6 · DAILY SIGNAL &nbsp;|&nbsp; 点个 <b>Star</b>，让下一轮自动化有迹可循</sub>
</div>
