# JavLibrary 定期爬虫 设计文档

## 概述

每天从 JavLibrary 抓取"最想要"(Most Wanted) 和"高评价"(Top Rated) 两榜单的第一页数据，提取作品详情，并通过 clg55.top 补全搜索链接和磁力链接，结果存入 SQLite，封面下载到本地。

## 数据流

```
cron/systemd timer 触发 (每天一次)
  └→ main.py 入口
       ├→ scraper.py: 用 cloakbrowser 依次抓取两个榜单页，解析 DOM
       │    └→ 提取: 番号、标题、演员、评分、封面URL、日期、时长、制作商、标签、排名
       ├→ scraper.py: 对每个新番号 + DB中缺磁力链接的旧番号(60天内)
       │    └→ 用 cloakbrowser 访问 clg55.top 搜索，获取搜索链接和磁力链接列表
       ├→ db.py: 写入 SQLite (番号+榜单去重，覆盖最新排名)
       └→ covers/: 下载封面图，以番号命名
```

## 项目结构

```
jav_ext/
├── main.py          # 入口：协调流程、日志
├── scraper.py       # JavLibrary 列表页解析 + clg55.top 搜索/磁力
├── db.py            # SQLite 初始化与 CRUD
├── config.py        # 外置 URL、代理、路径、限制天数等配置
├── covers/          # 封面图存储目录
├── data/            # SQLite 文件目录
└── requirements.txt
```

## 配置项 (config.py)

- `JAVLIBRARY_BASE_URL` — JavLibrary 基础地址
- `MOST_WANTED_URL` — 最想要榜单页完整 URL
- `TOP_RATED_URL` — 高评价榜单页完整 URL
- `SEARCH_BASE_URL` — clg55.top 搜索基础地址
- `PROXY` — 代理地址 (http://127.0.0.1:7897)
- `WAIT_DELAY` — 页面加载等待秒数
- `COVERS_DIR` — 封面图存储路径
- `DATA_DIR` — SQLite 文件路径
- `MAGNET_BACKFILL_DAYS` — 补漏磁力链接的时间范围 (默认 60 天)
- `REQUEST_RETRIES` — 网络请求重试次数 (默认 3)
- `PAGE_INTERVAL_MIN` / `PAGE_INTERVAL_MAX` — 请求之间的随机延迟范围 (默认 3-5 秒)

## 数据库设计

### videos 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| code | TEXT UNIQUE | 番号 |
| title | TEXT | 标题 |
| cover_url | TEXT | 封面图 URL |
| cover_path | TEXT | 本地封面图路径 |
| date | TEXT | 发行日期 |
| duration | TEXT | 时长 |
| maker | TEXT | 制作商 |
| label | TEXT | 标签 |
| score | REAL | 评分 |
| search_url | TEXT | clg55.top 搜索结果页 URL |
| created_at | TEXT | 首次入库时间 |
| updated_at | TEXT | 最后更新时间 |

### actresses 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| video_code | TEXT FK→videos.code | 番号 |
| name | TEXT | 演员名 |

### rankings 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| video_code | TEXT FK→videos.code | 番号 |
| list_type | TEXT | 榜单类型: most_wanted / top_rated |
| rank | INTEGER | 排名 |
| updated_at | TEXT | 更新时间 |

### magnets 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 |
| video_code | TEXT FK→videos.code | 番号 |
| magnet | TEXT | 磁力链接 |
| source | TEXT | 来源站点 |
| created_at | TEXT | 入库时间 |

## 核心逻辑

### 列表页抓取 (scraper.py)
1. cloakbrowser 打开榜单页
2. 等待 WAIT_DELAY 秒直到页面加载完成
3. 解析 DOM 提取列表项：遍历每部作品的 HTML 节点，提取番号、标题、演员、评分、封面URL、日期、时长、制作商、标签
4. 返回作品列表

### 磁力搜索 (scraper.py)
1. 用番号拼接 clg55.top 搜索 URL
2. cloakbrowser 打开搜索页（humanize=True，模拟真人操作）
3. 等待页面加载后解析 DOM，提取搜索页链接和磁力链接列表
4. 重试机制：单次请求最多重试 3 次
5. 每次搜索之间间隔 3-5 秒随机延迟

### 补漏逻辑 (main.py)
1. 抓取完新数据后，查询 DB 中缺少磁力链接的番号（created_at 在 60 天内）
2. 逐个尝试搜索磁力链接
3. 限制：每轮补漏最多尝试 20 个，避免过度请求

### 数据库写入 (db.py)
- videos: INSERT OR REPLACE 按番号去重
- actresses: 先删后插（按番号清空旧数据再写入）
- rankings: INSERT OR REPLACE 按 (番号, 榜单) 去重
- magnets: INSERT OR IGNORE 按 (番号, 磁力) 去重

### 封面下载
- 从 cover_url 下载图片，保存到 covers/ 目录
- 文件名: `{番号}.jpg`
- 下载失败不阻塞流程

## 错误处理
- 浏览器启动失败 → 记录错误日志并退出，让 cron 下次重试
- 页面加载超时 → 重试 3 次后跳过该榜单
- 磁力搜索失败 → 记录日志，不影响该番号数据写入
- 封面下载失败 → 记录日志，cover_path 留空

## 调度
- 由系统 cron 或 systemd timer 每天凌晨触发一次
- 示例 cron: `0 3 * * * cd /path/to/jav_ext && python main.py`
