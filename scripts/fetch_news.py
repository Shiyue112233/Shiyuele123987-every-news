#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日新闻简报生成器（生成整个静态站点）。

流程：抓取 RSS 源 -> 清洗去重 -> 按分类配额挑选约 20 条
      -> 生成站点 site/：今日首页、每日页、归档页、关于页、RSS
      -> 同时写出 data/news.json 与 data/archive/YYYY-MM-DD.json。

用法：
    python fetch_news.py              # 正常生成
    python fetch_news.py --limit 25   # 改条数
    python fetch_news.py --quiet      # 静默（供计划任务调用）

只依赖标准库。本机 HTTPS 被拦截，因此源清单以 http:// 为主。
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
SITE = ROOT / "site"
ASSETS = SITE / "assets"
DAILY = SITE / "daily"

TEMPLATE = HERE / "template.html"
ARCHIVE_TEMPLATE = HERE / "archive_template.html"
ABOUT_TEMPLATE = HERE / "about_template.html"
STYLE_SRC = HERE / "style.css"
SITE_TITLE = "每日简报"
# RSS 里需要绝对地址：本地默认 localhost，部署时用环境变量 SITE_URL 覆盖
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8080").rstrip("/")

CST = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTHS_CN = {m: i for i, m in enumerate(
    ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"], 1)}


# ---------------------------------------------------------------- 数据结构
@dataclass
class Item:
    title: str
    link: str
    source: str
    category: str
    published: datetime | None = None
    abstract: str = ""
    weight: int = 5
    tier: int = 2
    domain: str = ""
    also: list[str] = field(default_factory=list)
    peer_ids: list[int] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def sort_key(self) -> tuple:
        ts = self.published.timestamp() if self.published else 0
        # 多家来源互证过的条目小幅加权（真实性/重要性信号）
        score = self.weight + (1 if self.also else 0)
        return (score, -self.tier, ts)

    @property
    def source_count(self) -> int:
        return len({self.source} | set(self.also))


# ---------------------------------------------------------------- 文本工具
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t\u3000]+")


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"<!\[CDATA\[|\]\]>", "", raw)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = TAG_RE.sub("", s)
    s = html_mod.unescape(s)
    s = s.replace("\u200b", "").replace("\xa0", " ")
    s = WS_RE.sub(" ", s)
    return s.strip()


def norm_key(title: str) -> str:
    s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", title)
    return s.lower()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------- 抓取
def fetch(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def decode(raw: bytes) -> str:
    head = raw[:400].decode("ascii", errors="ignore").lower()
    for enc in ("utf-8", "gb18030", "gbk", "big5"):
        if enc in head.replace("-", ""):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                break
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_date(raw: str) -> datetime | None:
    """尽量宽容地解析各种时间格式（RFC822 / ISO8601 / 中文日期）。"""
    if not raw:
        return None
    s = clean_text(raw)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{2,4})\s+(\d{2}):(\d{2})(?::(\d{2}))?"
                  r"\s*([+-]\d{4}|GMT|UTC|Z)?", s)
    if m:
        day, mon, year, hh, mm, ss, tz = m.groups()
        year = int(year)
        if year < 100:
            year += 2000
        off = timedelta(0)
        if tz and tz not in ("GMT", "UTC", "Z"):
            sign = 1 if tz[0] == "+" else -1
            off = sign * timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
        try:
            return datetime(year, MONTHS[mon.lower()], int(day), int(hh), int(mm),
                            int(ss or 0), tzinfo=timezone(off)).astimezone(CST)
        except (ValueError, KeyError):
            pass
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?[T\s]?(\d{1,2})?:?(\d{2})?:?(\d{2})?", s)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        try:
            return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0),
                            int(ss or 0), tzinfo=CST)
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2})?:?(\d{2})?", s)
    if m:
        now = datetime.now(CST)
        mo, d, hh, mm = m.groups()
        try:
            dt = datetime(now.year, int(mo), int(d), int(hh or 0), int(mm or 0), tzinfo=CST)
            if dt > now + timedelta(days=1):
                dt = dt.replace(year=now.year - 1)
            return dt
        except ValueError:
            pass
    return None


ITEM_RE = re.compile(r"<(item|entry)\b[^>]*>(.*?)</\1>", re.S | re.I)


def tag_value(block: str, *names: str) -> str:
    for name in names:
        m = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", block, re.S | re.I)
        if m:
            val = clean_text(m.group(1))
            if val:
                return val
    return ""


def tag_attr(block: str, name: str, attr: str) -> str:
    m = re.search(rf"<{name}\b[^>]*\b{attr}=[\"']([^\"']+)[\"']", block, re.S | re.I)
    return html_mod.unescape(m.group(1)) if m else ""


def parse_feed(text: str, name: str, category: str, weight: int,
               tier: int = 2, domain: str = "") -> list[Item]:
    out: list[Item] = []
    for m in ITEM_RE.finditer(text):
        block = m.group(2)
        title = tag_value(block, "title")
        if not title or len(title) < 4:
            continue
        link = tag_value(block, "link", "guid") or tag_attr(block, "link", "href")
        if not link:
            link = tag_attr(block, "a", "href")
        published = None
        for tag in ("pubDate", "published", "updated", "dc:date", "date"):
            published = parse_date(tag_value(block, tag))
            if published:
                break
        abstract = tag_value(block, "description", "summary", "content")
        abstract = re.sub(r"\s+", " ", abstract)[:160]
        out.append(Item(title=title, link=link, source=name, category=category,
                        published=published, abstract=abstract, weight=weight,
                        tier=tier, domain=domain))
    return out


def gather(sources: list[dict]) -> tuple[list[Item], list[str], list[str]]:
    items: list[Item] = []
    ok: list[str] = []
    bad: list[str] = []

    def work(src: dict):
        try:
            raw = fetch(src["url"])
            text = decode(raw)
            host = (urllib.parse.urlparse(src["url"]).hostname or "").lower()
            if host.startswith("www."):
                host = host[4:]
            got = parse_feed(text, src["name"], src["category"],
                             int(src.get("weight", 5)), int(src.get("tier", 2)), host)
            return src, got, None
        except Exception as exc:  # noqa: BLE001
            return src, [], f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        for src, got, err in pool.map(work, sources):
            if err or not got:
                bad.append(f"{src['name']}({err or '无条目'})")
            else:
                ok.append(f"{src['name']} {len(got)}条")
                items.extend(got)
    return items, ok, bad


def mark_corroboration(items: list[Item]) -> None:
    """
    跨来源互证：同一事件被「不同域名」的多家媒体报道时，给这些条目打上 also 标记。
    页面会显示「多源 ×N」，排序时也小幅加权——这是本站在没法人工核实时的真实性信号。
    中文按「标题二元组」比，英文按「实词集合」比，避免两种语言互相误配。
    """
    zh: list[tuple[int, set[str]]] = []
    en: list[tuple[int, set[str]]] = []
    for idx, it in enumerate(items):
        key = norm_key(it.title)
        if len(key) >= 8 and _cjk_ratio(key) > 0.5:
            zh.append((idx, {key[p:p + 2] for p in range(len(key) - 1)}))
        else:
            toks = latin_tokens(it.title)
            if len(toks) >= 3:
                en.append((idx, toks))

    def pair_up(bucket: list[tuple[int, set[str]]], need: int, ratio: float) -> None:
        for x in range(len(bucket)):
            i, gi = bucket[x]
            for y in range(x + 1, len(bucket)):
                j, gj = bucket[y]
                a, b = items[i], items[j]
                if not a.domain or a.domain == b.domain:
                    continue
                inter = len(gi & gj)
                if inter >= need and inter / max(1, min(len(gi), len(gj))) >= ratio:
                    _link_peers(a, b)

    pair_up(zh, 6, 0.45)   # 中文：6 个以上共同二字词，且占比够高
    pair_up(en, 3, 0.45)   # 英文：3 个以上共同实词


def _cjk_ratio(s: str) -> float:
    if not s:
        return 0.0
    n = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return n / len(s)


STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "at", "is", "are",
    "was", "were", "be", "been", "with", "from", "by", "as", "it", "its", "this",
    "that", "these", "those", "new", "says", "say", "said", "after", "over", "into",
    "about", "how", "why", "what", "who", "when", "where", "will", "would", "could",
    "can", "may", "not", "no", "up", "down", "out", "but", "more", "most", "than",
    "then", "also", "has", "have", "had", "you", "your", "we", "our", "they", "their",
    "he", "she", "his", "her", "me", "us", "them", "here", "there", "one", "two",
}


def latin_tokens(title: str) -> set[str]:
    """取英文标题里的实词（3 字母以上、去停用词）。"""
    return {t for t in re.findall(r"[A-Za-z0-9]{3,}", (title or "").lower())
            if t not in STOPWORDS}


def _link_peers(a: Item, b: Item) -> None:
    a.also.append(b.source)
    b.also.append(a.source)
    a.peer_ids.append(id(b))
    b.peer_ids.append(id(a))


# ---------------------------------------------------------------- 挑选
def pick(items: list[Item], quotas: dict, limit: int, now: datetime) -> list[Item]:
    fresh_cut = now - timedelta(hours=48)
    week_cut = now - timedelta(days=7)

    def is_fresh(it: Item) -> bool:
        return bool(it.published and it.published >= fresh_cut)

    def three_grams(s: str) -> set[str]:
        return {s[i:i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else set()

    seen_titles: list[str] = []
    seen_grams: list[set[str]] = []
    seen_links: set[str] = set()
    chosen_ids: set[int] = set()

    def accept(it: Item) -> bool:
        if not it.title or not it.link:
            return False
        key = norm_key(it.title)
        if not key:
            return False
        if it.link in seen_links:
            return False
        # 同一事件已经收录过一条（多源互证过的同伴），就不重复占位
        if any(pid in chosen_ids for pid in it.peer_ids):
            return False
        grams = three_grams(key)
        for s, g in zip(seen_titles, seen_grams):
            if key[:14] == s[:14]:
                return False
            if len(s) > 10 and similar(key, s) > 0.82:
                return False
            # 同一事件被不同媒体改写标题：共享三元组足够多也算重复
            if similar(key, s) > 0.72:
                return False
        seen_titles.append(key)
        seen_grams.append(grams)
        seen_links.add(it.link)
        chosen_ids.add(id(it))
        return True

    pool = sorted(items, key=lambda x: x.sort_key, reverse=True)
    chosen: list[Item] = []

    def interleave(cands: list[Item]) -> list[Item]:
        """同一分类内按来源轮转，避免整栏被单一站点占满。"""
        buckets: dict[str, list[Item]] = {}
        for it in cands:
            buckets.setdefault(it.source, []).append(it)
        mixed: list[Item] = []
        while buckets:
            for src in list(buckets):
                mixed.append(buckets[src].pop(0))
                if not buckets[src]:
                    del buckets[src]
        return mixed

    for cat, quota in quotas.items():
        cands = [it for it in pool if it.category == cat and is_fresh(it)]
        if len(cands) < quota:
            cands += [it for it in pool if it.category == cat and not is_fresh(it)]
        cands = interleave(cands)
        taken = 0
        for it in cands:
            if taken >= quota or len(chosen) >= limit:
                break
            if accept(it):
                chosen.append(it)
                taken += 1

    if len(chosen) < limit:
        for it in pool:
            if len(chosen) >= limit:
                break
            if it.published and it.published < week_cut:
                continue
            if accept(it):
                chosen.append(it)

    if len(chosen) < limit:  # 兜底：放宽到任意时间
        for it in pool:
            if len(chosen) >= limit:
                break
            if accept(it):
                chosen.append(it)

    return chosen


# ---------------------------------------------------------------- 渲染
def esc(s: str) -> str:
    return html_mod.escape(s or "", quote=True)


def safe_link(url: str) -> str:
    if re.match(r"^https?://", url or "", re.I):
        return url
    return "#"


def rel_time(dt: datetime | None, now: datetime) -> str:
    if not dt:
        return "时间未知"
    delta = now - dt
    secs = delta.total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))} 分钟前"
    if secs < 86400:
        return f"{int(secs // 3600)} 小时前"
    if secs < 86400 * 2:
        return "昨天"
    return dt.strftime("%m-%d %H:%M")


CAT_ORDER = ["要闻", "国际", "财经", "科技", "AI", "科学", "社会", "教育", "体育", "商业"]


def render_daily(template: str, chosen: list[Item], meta: dict, prefix: str,
                 prev_date: str | None, next_date: str | None,
                 active: str = "today") -> str:
    now = meta["now"]
    by_cat: dict[str, list[Item]] = {}
    for it in chosen:
        by_cat.setdefault(it.category, []).append(it)

    order = [c for c in CAT_ORDER if c in by_cat] + [c for c in by_cat if c not in CAT_ORDER]
    sections = []
    for cat in order:
        rows = by_cat[cat]
        lis = []
        for it in rows:
            ts = rel_time(it.published, now)
            abs_time = it.published.strftime("%m-%d %H:%M") if it.published else ""
            abstract = f'<div class="abstract">{esc(it.abstract)}</div>' if len(it.abstract) > 30 else ""
            peers = sorted({it.source} | set(it.also))
            multi = ""
            if len(peers) > 1:
                other = sorted(set(it.also))
                tip = "、".join(other[:5]) + ("…" if len(other) > 5 else "")
                multi = (f'<span class="chip multi" title="另有多家来源报道：{esc(tip)}">'
                         f'多源 ×{len(peers)}</span>')
            lis.append(
                '<li>'
                f'<a class="title" href="{esc(safe_link(it.link))}" target="_blank" rel="noopener">{esc(it.title)}</a>'
                f'{abstract}'
                f'<div class="meta"><span class="chip">{esc(it.source)}</span>'
                f'{multi}'
                f'<span title="{esc(abs_time)}">{esc(ts)}</span></div>'
                '</li>'
            )
        sections.append(
            f'<section class="cat"><div class="cat-head">'
            f'<span class="name">{esc(cat)}</span><span class="rule"></span>'
            f'<span class="count">{len(rows)} 条</span></div>'
            f'<ol class="news">{"".join(lis)}</ol></section>'
        )

    status = meta["status"]
    status_txt = f'成功 {len(status["ok"])} 个源；失败 {len(status["bad"])} 个' if status["bad"] else \
                 f'成功 {len(status["ok"])} 个源，全部正常'
    if status["bad"]:
        status_txt += "（" + "、".join(status["bad"][:4]) + "）"

    if prev_date:
        pager_prev = (f'<a href="{prefix}daily/{prev_date}.html">← '
                      f'{prev_date[5:]} 的前一期</a>')
    else:
        pager_prev = '<span class="disabled">← 已是最早一期</span>'
    if next_date:
        pager_next = (f'<a href="{prefix}daily/{next_date}.html">'
                      f'{next_date[5:]} 的下一期 →</a>')
    else:
        pager_next = '<span class="disabled">已是最新一期 →</span>'

    repl = {
        "{{ROOT}}": prefix,
        "{{ACTIVE_TODAY}}": "active" if active == "today" else "",
        "{{ACTIVE_ARCHIVE}}": "active" if active == "archive" else "",
        "{{ACTIVE_ABOUT}}": "active" if active == "about" else "",
        "{{PAGER_PREV}}": pager_prev,
        "{{PAGER_NEXT}}": pager_next,
        "{{DATE_CN}}": now.strftime("%Y年%m月%d日"),
        "{{WEEKDAY_CN}}": WEEKDAYS[now.weekday()],
        "{{GENERATED_AT}}": now.strftime("%Y-%m-%d %H:%M"),
        "{{TOTAL}}": str(len(chosen)),
        "{{QUOTE_TEXT}}": esc(meta["quote"]["text"]),
        "{{QUOTE_AUTHOR}}": esc(meta["quote"]["author"]),
        "{{TOOL_NAME}}": esc(meta["tool"]["name"]),
        "{{TOOL_CATEGORY}}": esc(meta["tool"]["category"]),
        "{{TOOL_PRICE}}": esc(meta["tool"]["price"]),
        "{{TOOL_DESC}}": esc(meta["tool"]["desc"]),
        "{{TOOL_URL}}": esc(safe_link(meta["tool"]["url"])),
        "{{NEWS_SECTIONS}}": "\n".join(sections),
        "{{SOURCE_LIST}}": esc("、".join(sorted({it.source for it in chosen}))),
        "{{FETCH_STATUS}}": esc(status_txt),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def all_issues() -> list[dict]:
    """读取所有历史快照，按日期倒序返回。"""
    issues: list[dict] = []
    if not ARCHIVE.exists():
        return issues
    for path in sorted(ARCHIVE.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        date = path.stem
        payload["_date"] = date
        payload["_file"] = path
        issues.append(payload)
    return issues


def build_archive(issues: list[dict], per_page: int = 20) -> str:
    template = ARCHIVE_TEMPLATE.read_text(encoding="utf-8")
    cards = []
    for it in issues:
        date = it["_date"]
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            weekday = WEEKDAYS[dt.weekday()]
            title = f"{dt.year}年{dt.month}月{dt.day}日"
        except ValueError:
            weekday, title = "", date
        first = ""
        if it.get("items"):
            first = esc(it["items"][0]["title"])
        cards.append(
            f'<a class="arch-card" href="daily/{date}.html">'
            f'<div class="d">{title}</div>'
            f'<div class="w">{weekday}</div>'
            f'<div class="n">{it.get("count", 0)} 条</div>'
            f'<div class="first">{first}</div></a>'
        )
    return (template
            .replace("{{CARDS}}", "\n".join(cards))
            .replace("{{COUNT}}", str(len(issues)))
            .replace("{{PER_PAGE}}", str(per_page)))


def build_feed(issues: list[dict], limit: int = 20) -> str:
    """生成 RSS：每期一条，摘要为当期头条列表。"""
    def rfc822(date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=6, minute=30, tzinfo=CST)
        except ValueError:
            dt = datetime.now(CST)
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0800")

    items = []
    for it in issues[:limit]:
        date = it["_date"]
        titles = "".join(f"<li>{esc(x['title'])}</li>"
                         for x in it.get("items", [])[:20])
        desc = (f"<p>{esc(it.get('quote', {}).get('text', ''))}</p>"
                f"<ul>{titles}</ul>")
        items.append(
            "<item>"
            f"<title>{esc(SITE_TITLE)} · {date}</title>"
            f"<link>{SITE_URL}/daily/{date}.html</link>"
            f"<guid isPermaLink=\"false\">{SITE_URL}/daily/{date}.html</guid>"
            f"<pubDate>{rfc822(date)}</pubDate>"
            f"<description><![CDATA[{desc}]]></description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{esc(SITE_TITLE)}</title>"
        f"<link>{SITE_URL}/index.html</link>"
        "<description>每天约 20 条精选资讯，配一条寄语与一个工具推荐。</description>"
        "<language>zh-CN</language>"
        + "".join(items) +
        "</channel></rss>\n"
    )


def issue_to_items(issue: dict) -> list[Item]:
    """把历史快照里的条目还原成 Item，用于重新渲染往期页面。"""
    out: list[Item] = []
    for x in issue.get("items", []):
        it = Item(title=x.get("title", ""), link=x.get("link", ""),
                  source=x.get("source", ""), category=x.get("category", "要闻"),
                  abstract=x.get("abstract", ""), weight=5,
                  tier=int(x.get("tier", 2) or 2),
                  also=list(x.get("also", []) or []))
        if x.get("published"):
            try:
                it.published = datetime.fromisoformat(x["published"])
            except ValueError:
                pass
        if it.title:
            out.append(it)
    return out


def build_site(chosen: list[Item], meta: dict, limit: int) -> None:
    """生成 site/ 下的全部页面（往期页面也一并按当前模板重渲染，保证样式与链接一致）。"""
    SITE.mkdir(parents=True, exist_ok=True)
    DAILY.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    ASSETS.joinpath("style.css").write_text(STYLE_SRC.read_text(encoding="utf-8"), encoding="utf-8")

    issues = all_issues()
    today = meta["now"].strftime("%Y-%m-%d")
    dates = [it["_date"] for it in issues]           # 已按日期倒序
    if today not in dates:
        dates.insert(0, today)
    idx = dates.index(today)
    template = TEMPLATE.read_text(encoding="utf-8")

    for i, date in enumerate(dates):
        newer = dates[i - 1] if i > 0 else None
        older = dates[i + 1] if i + 1 < len(dates) else None
        if date == today:
            items, issue_meta = chosen, meta
        else:
            issue = next(x for x in issues if x["_date"] == date)
            items = issue_to_items(issue)
            gen = issue.get("generated_at", "")
            try:
                gen_dt = datetime.fromisoformat(gen)
            except ValueError:
                gen_dt = datetime.strptime(date, "%Y-%m-%d").replace(hour=6, minute=30, tzinfo=CST)
            issue_meta = {
                "now": gen_dt,
                "quote": issue.get("quote", {"text": "", "author": ""}),
                "tool": issue.get("tool", {"name": "", "category": "", "price": "", "desc": "", "url": ""}),
                "status": {"ok": issue.get("sources_ok", []), "bad": issue.get("sources_failed", [])},
            }
        page = render_daily(template, items, issue_meta, "../",
                            prev_date=older, next_date=newer, active="")
        DAILY.joinpath(f"{date}.html").write_text(page, encoding="utf-8")
        if date == today:
            SITE.joinpath("index.html").write_text(
                render_daily(template, items, issue_meta, "",
                             prev_date=older, next_date=newer, active="today"),
                encoding="utf-8")

    SITE.joinpath("archive.html").write_text(build_archive(issues, limit), encoding="utf-8")
    SITE.joinpath("about.html").write_text(
        ABOUT_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    SITE.joinpath("feed.xml").write_text(build_feed(issues), encoding="utf-8")


# ---------------------------------------------------------------- 主流程
def daily_index(now: datetime) -> int:
    return now.timetuple().tm_yday + now.year * 366


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成每日新闻日报")
    ap.add_argument("--limit", type=int, default=20, help="新闻条数，默认 20")
    ap.add_argument("--quiet", action="store_true", help="静默模式")
    args = ap.parse_args(argv)

    now = datetime.now(CST)
    src_conf = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    quotes = json.loads((DATA / "quotes.json").read_text(encoding="utf-8"))["quotes"]
    tools = json.loads((DATA / "tools.json").read_text(encoding="utf-8"))["tools"]

    items, ok, bad = gather(src_conf["sources"])
    mark_corroboration(items)
    chosen = pick(items, src_conf["分类配额"], args.limit, now)

    idx = daily_index(now)
    quote = quotes[idx % len(quotes)]
    tool = tools[idx % len(tools)]

    meta = {"now": now, "quote": quote, "tool": tool, "status": {"ok": ok, "bad": bad}}

    payload = {
        "generated_at": now.isoformat(),
        "count": len(chosen),
        "quote": quote,
        "tool": tool,
        "sources_ok": ok,
        "sources_failed": bad,
        "items": [
            {
                "title": it.title, "link": it.link, "source": it.source,
                "category": it.category,
                "published": it.published.isoformat() if it.published else None,
                "abstract": it.abstract,
                "tier": it.tier,
                "also": sorted(set(it.also)),
            } for it in chosen
        ],
    }
    (DATA / "news.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    (ARCHIVE / f"{now.strftime('%Y-%m-%d')}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    build_site(chosen, meta, args.limit)
    # 兼容旧入口：双击本目录的 index.html 自动跳到站点首页
    (ROOT / "index.html").write_text(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
        '<meta http-equiv="refresh" content="0; url=site/index.html">'
        '<title>每日简报</title></head><body>'
        '<p>正在打开每日简报…… 若没有自动跳转，请点 '
        '<a href="site/index.html">这里</a>。</p></body></html>',
        encoding="utf-8")

    if not args.quiet:
        print(f"[{now.strftime('%Y-%m-%d %H:%M')}] 抓取源 {len(src_conf['sources'])} 个："
              f"成功 {len(ok)}，失败 {len(bad)}")
        for b in bad:
            print("   失败:", b)
        print(f"候选条目 {len(items)} 条 -> 最终收录 {len(chosen)} 条")
        for i, it in enumerate(chosen, 1):
            t = it.published.strftime("%m-%d %H:%M") if it.published else "时间未知"
            print(f"  {i:2d}. [{it.category}] {it.title[:44]:<44s} | {it.source} | {t}")
        print(f"\n寄语：{quote['text']} —— {quote['author']}")
        print(f"工具：{tool['name']}（{tool['category']}）")
        print(f"\n站点已生成：{SITE / 'index.html'}")
        print(f"历史期数：{len(all_issues())} 期，归档页：{SITE / 'archive.html'}")
    return 0 if chosen else 1


if __name__ == "__main__":
    sys.exit(main())
