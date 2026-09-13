# 每日简报

一个每天自动更新的个人新闻站：约 20 条精选资讯 + 每日寄语 + 工具推荐。

## 在线地址

部署在 GitHub Pages 上：见仓库 Settings → Pages 里显示的地址，形如
`https://<你的用户名>.github.io/<仓库名>/`

## 它是怎么运转的

```
每天 06:30（北京时间）
  → GitHub Actions 运行 scripts/fetch_news.py
  → 抓取公开新闻源、筛选去重、生成静态站点到 site/
  → 自动提交当天快照，并发布到 GitHub Pages
```

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `site/` | 生成的网站（发布的就是这个目录） |
| `site/index.html` | 首页（今日） |
| `site/daily/YYYY-MM-DD.html` | 每一期 |
| `site/archive.html` | 归档索引 |
| `site/feed.xml` | RSS 订阅 |
| `scripts/fetch_news.py` | 抓取 + 生成站点 |
| `scripts/template.html` 等 | 页面模板 |
| `data/sources.json` | 新闻源清单与分类配额 |
| `data/quotes.json` / `data/tools.json` | 寄语库 / 工具库 |
| `data/archive/YYYY-MM-DD.json` | 每期数据快照 |
| `.github/workflows/daily.yml` | 自动更新与发布流程 |

## 本地怎么看

双击 `打开网站.cmd`，浏览器会打开 `http://localhost:8080`；
或者直接双击 `site/index.html`。

## 想改内容

- 换新闻源 / 改每类条数：编辑 `data/sources.json`
- 换寄语、换工具推荐：编辑 `data/quotes.json`、`data/tools.json`
- 改配色与排版：编辑 `scripts/style.css`，重跑脚本后全站生效
- 手动更新一次：`python scripts/fetch_news.py`

## 说明

- 纯静态站点，不追踪、不收集任何信息。
- 新闻标题与摘要版权归原媒体所有，点击可跳转原文。
- 脚本只依赖 Python 标准库。
