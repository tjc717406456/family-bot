# Google Family Bot

Google 家庭组自动化管理工具，支持 Web 界面和 CLI 命令行两种操作方式。

自动完成：Google 账号登录 → Gemini 开通 → 家庭组邀请接受 → Antigravity OAuth 授权。

## 环境要求

- Python 3.10+
- Google Chrome 浏览器（已安装在本机）
- Windows / macOS / Linux

## 部署

```bash
# 克隆项目
git clone https://github.com/tjc717406456/family-bot.git
cd family-bot

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器驱动
playwright install chromium
```

## 启动

### Web 界面（推荐）

```bash
python run_web.py
```

浏览器访问 http://localhost:5000

### CLI 命令行

```bash
python main.py --help
```

## 使用流程

### 1. 添加家长账号

进入"家长管理"页面，添加家长的 Google 邮箱和密码。

### 2. 添加成员账号

进入"成员管理"页面，选择所属家长，填入成员邮箱、密码、TOTP 密钥（有 2FA 的填，没有可不填）。

### 3. 执行自动化任务

进入"任务管理"页面，支持全量执行、按家长执行、按成员执行。

自动化流程会依次完成：
1. **Google 登录** — 使用成员邮箱密码登录，支持 2FA
2. **Gemini 开通** — 自动访问 Gemini 并完成激活
3. **家庭组加入** — 在 Gmail 中查找邀请邮件并接受

成员状态流转：`pending` → `gemini_done` → `joined`

### 4. Antigravity OAuth（可选）

成员状态为 `joined` 后可用：
1. 在成员列表顶部粘贴 OAuth 链接
2. 点击对应成员的"Antigravity"按钮
3. 自动完成 OAuth 授权，回调 URL 写入备注栏
4. 点击"复制"按钮获取回调 URL

## CLI 命令参考

```bash
# 家长管理
python main.py parent add --email xxx@gmail.com --password xxx
python main.py parent list

# 成员管理
python main.py member add --parent-id 1 --email xxx@gmail.com --password xxx
python main.py member list

# 执行任务
python main.py run member <member_id>
python main.py run parent <parent_id>
python main.py run all

# 查看状态
python main.py status
```

## 项目结构

```
family-bot/
├── automation/          # 自动化脚本
│   ├── google_login.py      # Google 账号登录
│   ├── gemini_activate.py   # Gemini 开通激活
│   ├── family_accept.py     # 家庭组邀请接受
│   └── antigravity_login.py # Antigravity OAuth 登录
├── cli/                 # CLI 命令行工具
├── web/                 # Web 管理界面（Flask）
│   ├── routes/              # 路由（家长、成员、任务）
│   ├── templates/           # 页面模板
│   └── task_manager.py      # 后台任务管理
├── db/                  # 数据库（SQLAlchemy + SQLite）
├── data/                # 运行时数据（自动生成）
│   ├── family_bot.db        # SQLite 数据库
│   ├── chrome_profiles/     # 成员独立 Chrome 配置
│   └── screenshots/         # 自动化过程截图
├── config.py            # 全局配置
├── run_web.py           # Web 服务入口
├── main.py              # CLI 入口
└── requirements.txt     # Python 依赖
```

## 配置说明

配置项在 `config.py` 中：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `BROWSER_HEADLESS` | `False` | 是否无头模式运行浏览器 |
| `BROWSER_SLOW_MO` | `500` | 操作间隔（毫秒），便于观察 |
| `BROWSER_CHANNEL` | `chrome` | 使用本机 Chrome |

## 注意事项

- `data/` 目录包含数据库和浏览器配置，已被 `.gitignore` 排除
- 每个成员使用独立的 Chrome Profile，互不干扰
- 首次运行时 `data/` 目录会自动创建
- 执行自动化任务时浏览器会弹出窗口，请勿手动操作
