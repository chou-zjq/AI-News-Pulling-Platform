# 🤖 AI 新闻调取平台

自动抓取、整理 AI 相关新闻，生成每日 Markdown 记录本。
**前端采用 GSAP 动画引擎，提供流畅的交互体验。**

## 快速开始

### 1. 环境要求

- Python 3.11+
- 浏览器（Chrome / Edge / Firefox）

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 Key
# - NewsAPI: https://newsapi.org/register
# - GitHub Token: https://github.com/settings/tokens
```

### 4. 启动后端

```bash
cd backend
python main.py
# 服务运行在 http://127.0.0.1:8000
```

### 5. 打开前端

直接用浏览器打开 `frontend/index.html`，或：

```bash
cd frontend
python -m http.server 3000
# 访问 http://127.0.0.1:3000
```

## 项目结构

```
AI新闻调取平台/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── models/
│   │   ├── news.py          # NewsItem 数据模型
│   │   ├── database.py      # SQLite 数据库
│   │   └── keybox.py        # KeyBox Provider 注册表
│   ├── services/
│   │   ├── fetcher.py       # 新闻抓取（NewsAPI + GitHub）
│   │   ├── recorder.py      # Markdown 记录本生成
│   │   └── keyvault.py      # KeyVault 加密服务
│   ├── routers/
│   │   ├── api.py           # 新闻 API 路由
│   │   └── keybox_api.py    # KeyBox 管理路由
│   └── requirements.txt
├── frontend/
│   ├── index.html           # 单文件前端（GSAP CDN 引入）
│   ├── style.css            # 样式（GPU 加速 + CSS 变量）
│   ├── app.js               # 主逻辑 + GSAP 动画编排
│   └── components/
│       └── key-manager.js   # KeyBox 面板（含 GSAP 微交互）
├── data/                    # 运行时生成
│   ├── news_index.db        # SQLite 数据库
│   ├── .keybox-secret       # Fernet 密钥（权限 600）
│   └── RecordLibrary/       # Markdown 记录库
│       └── 2026/06/2026-06-08.md
├── tests/
│   ├── test_keyvault.py
│   └── test_fetcher.py
└── .env.example
```

## API 文档

启动后端后访问：http://127.0.0.1:8000/docs

### 主要端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/news/fetch` | 抓取当日 AI 新闻（支持 `?force=true`） |
| GET | `/api/records?date=YYYY-MM-DD` | 获取指定日期记录本 |
| GET | `/api/records/history` | 历史记录树形导航 |
| GET | `/api/keys/providers` | 列出支持的 AI Provider |
| GET | `/api/keys` | 列出已保存的 Key（脱敏） |
| POST | `/api/keys` | 添加新 Key |
| DELETE | `/api/keys/{id}` | 删除 Key |
| POST | `/api/keys/{id}/test` | 测试 Key 有效性 |

## 运行测试

```bash
cd backend
pytest ../tests/ -v
```

## 分阶段开发进度

- [x] 第一阶段：API 调用与新闻抓取
- [x] 第二阶段：热度排序与前 20 筛选
- [x] 第三阶段：记录本生成与存储
- [x] 第四阶段：前端界面
- [x] 第五阶段：历史记录浏览
- [x] KeyBox：API Key 管理模块
