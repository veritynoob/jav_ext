# JavLibrary 管理面板 设计文档

## 概述

为现有 JAV 爬虫新增 FastAPI + Jinja2 + HTMX 的 Web 管理面板，提供数据浏览、搜索筛选、CRUD、统计面板、演员聚合和磁力管理功能，使用简单密码保护。

## 技术栈

- **后端**: FastAPI (异步原生支持)
- **模板**: Jinja2 (服务端渲染)
- **前端交互**: HTMX (CDN 引入，局部刷新)
- **CSS**: Pico.css (classless CSS，CDN 引入)
- **鉴权**: Signed cookie + 环境变量配置密码
- **数据库**: 复用现有 SQLite schema，零改动

## 项目结构

```
jav_ext/
├── src/                    # 所有应用代码
│   ├── main.py             # 现有爬虫入口（不变）
│   ├── scraper.py          # 现有解析逻辑（不变）
│   ├── db.py               # 现有数据库层（不变）
│   ├── config.py           # 扩增 Web 配置项
│   ├── downloader.py       # 现有封面下载（不变）
│   ├── page_utils.py       # 现有 CF 绕过（不变）
│   └── web/                # 新增：FastAPI Web 面板
│       ├── __init__.py
│       ├── app.py           # FastAPI 实例、中间件、启动
│       ├── auth.py          # 鉴权中间件 + cookie 管理
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── dashboard.py    # 统计面板首页
│       │   ├── videos.py       # 视频列表、详情、编辑
│       │   ├── actresses.py    # 演员聚合页
│       │   ├── magnets.py      # 磁力链接管理
│       │   └── tasks.py        # 手动触发抓取/补漏
│       ├── templates/
│       │   ├── base.html       # 公共布局（侧边栏、导航、Toast）
│       │   ├── dashboard.html  # 统计数字卡片 + 榜单表格 + 最近添加
│       │   ├── videos.html     # 视频表格 + 搜索 + 分页 + 排序
│       │   ├── video_detail.html  # 单个视频完整信息
│       │   ├── actresses.html  # 演员列表按作品数排序
│       │   ├── magnets.html    # 缺磁力视频管理
│       │   └── login.html      # 登录页
│       └── static/
├── covers/                 # 现有封面存储
├── data/                   # 现有 SQLite 数据
├── tests/                  # 现有测试
└── requirements.txt        # 增补 fastapi, uvicorn, python-multipart
```

## 配置项 (config.py 增补)

```python
WEB_HOST = os.environ.get("JAV_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.environ.get("JAV_WEB_PORT", "8000"))
WEB_PASSWORD = os.environ.get("JAV_WEB_PASSWORD", "admin")
WEB_SECRET_KEY = os.environ.get("JAV_WEB_SECRET_KEY", "change-me-in-production")
```

## 路由设计

| 路径 | 方法 | 功能 |
|------|------|------|
| `/login` | GET/POST | 登录页，表单提交密码 |
| `/logout` | GET | 清除 cookie 跳回登录页 |
| `/` | GET | 统计面板首页 |
| `/videos` | GET | 视频列表（搜索、筛选、分页），HTMX 局部刷新 |
| `/videos/{code}` | GET | 单个视频详情 + 演员列表 + 磁力列表 |
| `/videos/{code}/edit` | GET/POST | 编辑视频信息（行内 HTMX） |
| `/actresses` | GET | 演员聚合页，按作品数量排序，点击展开作品列表 |
| `/magnets` | GET | 磁力链接管理，展示缺磁力视频，支持单个/批量触发搜索 |
| `/tasks/scrape` | POST | 手动触发榜单抓取（后台线程），HTMX polling 返回状态 |
| `/tasks/backfill` | POST | 手动触发磁力补漏（后台线程），同上 |

## 鉴权流

```
所有请求 → auth 中间件检查 cookie
  ├→ 无有效 cookie → 重定向 /login
  └→ 有效 cookie → 正常处理
/login POST → 验证密码 → 正确则 set signed cookie → 跳转 /
```

- 密码通过环境变量 `WEB_PASSWORD` 设置
- 使用 Starlette 的 `SessionMiddleware` 管理 signed cookie
- 固定单密码模式，无需用户注册

## 模板与 HTMX 交互

### base.html — 公共布局
- 顶部导航栏：Logo、侧边栏展开按钮
- 左侧边栏：📊面板 / 🎬视频 / 👩演员 / 🧲磁力 / ⚙️任务
- 侧边栏链接使用 `hx-get` + `hx-target="#main"` 局部加载
- 顶部搜索框：输入番号/标题 → `hx-get="/videos?q=..." hx-target="#main"`
- 底部 Toast 容器：操作反馈通过 `HX-Trigger` 响应头触发

### dashboard.html — 统计面板
- 数字卡片：总视频数、总演员数、今日新增、缺磁力数量
- 榜单排名简表（most_wanted / top_rated 各前 10）
- 最近添加视频列表（前 10 条）

### videos.html — 视频列表
- 表格列：番号、标题、封面缩略图、评分、日期、制作商、榜单排名
- 分页：HTMX 局部刷新 `#video-table`
- 排序：点击列头切换排序（score, date, code）
- 筛选：榜单类型、日期范围下拉
- 每行操作：详情链接、行内编辑、删除（确认后提交）

### video_detail.html — 视频详情
- 封面大图、完整元数据
- 演员标签（可点击跳演员聚合）
- 磁力链接列表（可复制）
- 编辑按钮触发 HTMX 行内编辑表单

### actresses.html — 演员聚合
- 演员列表按作品数量降序
- 点击某演员展开其作品列表（HTMX lazy load）

### magnets.html — 磁力管理
- 缺磁力视频列表（番号、标题、操作按钮）
- 单个触发：`POST /tasks/search-magnet/{code}` → HTMX 替换该行
- 批量触发：勾选多行 → 后台线程 → HTMX polling 进度

### login.html — 登录页
- 居中登录卡片
- 密码输入框 + 登录按钮
- 密码错误时显示红色错误提示

## 后台任务

手动触发抓取/补漏时，使用 `threading.Thread` 在后台执行现有 `main.py` 的核心逻辑：

- 任务状态存入内存字典 `{task_id: {status, progress, error}}`
- 前端 HTMX polling 每隔几秒请求 `/tasks/status/{task_id}`，获取进度并更新 UI
- 任务完成后状态标记为 `done` 或 `error`，停止 polling

## 错误处理

- **数据库不可用** → 所有路由捕获异常，返回 500 错误页 + 日志
- **后台任务失败** → 状态字典记录 error，HTMX polling 拉到错误信息展示在页面
- **鉴权失败** → cookie 无效返回 401，重定向 /login
- **表单验证** → 编辑提交字段校验失败，返回 HTMX partial 带错误提示
- **404** → 番号不存在返回 404 模板
- **CF 绕过失败** → 手动触发抓取任务状态为 error，展示失败原因

## 测试计划

| 层级 | 内容 |
|------|------|
| 路由测试 | FastAPI TestClient 测每个 endpoint 的 GET/POST 响应码、模板渲染、重定向 |
| 鉴权测试 | 无 cookie 拒绝访问、正确密码放行、错误密码拒绝 |
| HTMX 测试 | 验证局部响应的 `HX-Trigger` 头、partial HTML 内容 |
| DB 集成测试 | 临时 SQLite 验证 CRUD 操作 |
| 任务测试 | 模拟后台爬虫触发和状态轮询 |
