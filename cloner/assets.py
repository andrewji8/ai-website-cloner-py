"""资源发现、下载与 HTML 地址改写。

覆盖：
  - 常规资源属性 src / href / poster（P0 之前已有）
  - 响应式图片 srcset（P0：按逗号拆 URL，逐个下载，改写时保留 w/x 描述符）
  - CSS url(...) 引用
  - 站点级跨页 <a href> 改写（P0：把已爬取路由映射为相对路径）

合规说明：仅用于你有权复制 / 学习 / 迁移自有站点，请遵守目标站点 ToS 与版权。
"""
from __future__ import annotations

import html as _html
import posixpath
import re
import urllib.parse
import urllib.request
from pathlib import Path

# 需要本地化的资源属性：img.src、link.href、script.src、video/poster、source.src 等。
# 分组：(1)=属性名, (2)=引号, (3)=属性值
_ATTR_PATTERN = re.compile(
    r"\b(src|href|poster)\s*=\s*([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL
)
# CSS 中的 url(...) 引用（内联样式 / 资源）
_URL_FN_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
# 响应式图片 srcset："u1 320w, u2 640w, u3 1x, u4 2x"
_SRCSET_PATTERN = re.compile(r"\b(srcset)\s*=\s*([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)
# <a> 标签（用于跨页链接改写，只在标签内找 href）
_A_TAG_PATTERN = re.compile(r"<a\b[^>]*>", re.IGNORECASE | re.DOTALL)
_HREF_PATTERN = re.compile(r"\b(href)\s*=\s*([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)

# 明确跳过（无本地化价值 / 易膨胀）的后缀。
# P1：不再跳过 .json，以便本地化 Next.js 等框架被直接引用的路由数据。
_SKIPPED_EXT = {".ico", ".pem", ".sql", ".map", ".xml", ".woff2.map"}

# 站点级多页爬取时，页面之间的 <a href> 走 link_map，不应再当作"资源"下载。
_PAGE_EXTS = {".html", ".htm"}


def _is_data_uri(value: str) -> bool:
    return value.startswith("data:")


def _is_skip(ext: str) -> bool:
    return ext.lower() in _SKIPPED_EXT or ext == ""


def parse_srcset(value: str) -> list[str]:
    """把 srcset 值拆成 URL 列表（每个逗号分组取第一个空白分隔 token）。"""
    urls: list[str] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        url = part.split()[0]
        if url:
            urls.append(url)
    return urls


def normalize_url(raw: str, base_url: str, extra_skip: set[str] | None = None) -> str | None:
    """把相对地址解析成绝对 URL；不可用的（data:、空、skip 后缀）返回 None。"""
    raw = raw.strip()
    if not raw or _is_data_uri(raw) or raw.startswith(
        ("#", "mailto:", "tel:", "javascript:")
    ):
        return None
    url = urllib.parse.urljoin(base_url, raw)
    path = urllib.parse.urlsplit(url).path
    ext = posixpath.splitext(path)[1]
    if _is_skip(ext):
        return None
    if extra_skip and ext.lower() in extra_skip:
        return None
    return url


def same_origin(url: str, base_url: str) -> bool:
    return urllib.parse.urlsplit(url).netloc == urllib.parse.urlsplit(base_url).netloc


def discover_html_assets(
    html: str, base_url: str, extra_skip: set[str] | None = None
) -> list[str]:
    """从 HTML 文本中找出全部可本地化资源（去重、保序，含 srcset 内每张图）。"""
    found: set[str] = set()
    ordered: list[str] = []

    def add(url):
        if url and url not in found:
            found.add(url)
            ordered.append(url)

    for _attr, _quote, value in _ATTR_PATTERN.findall(html):
        add(normalize_url(_html.unescape(value), base_url, extra_skip))
    for _attr, _quote, value in _SRCSET_PATTERN.findall(html):
        for u in parse_srcset(_html.unescape(value)):
            add(normalize_url(u, base_url, extra_skip))
    for _q, value in _URL_FN_PATTERN.findall(html):
        add(normalize_url(_html.unescape(value), base_url, extra_skip))
    return ordered


def local_relpath(url: str) -> str:
    """把 URL 的路径部分映射为本地相对路径（保留目录结构）。"""
    parts = urllib.parse.urlsplit(url)
    path = parts.path.lstrip("/")
    if not path:
        path = "index.html"
    if not posixpath.splitext(path)[1]:
        path += ".bin"
    # 去除非 ASCII / 空格，避免 Windows 路径问题
    safe = re.sub(r"[^\w\-./]", "_", path)
    safe = safe.lstrip("./")
    return safe


def download(url: str, dest_root: Path, headers: dict[str, str] | None = None, timeout: int = 20) -> Path:
    """下载单个资源到 dest_root 下 local_relpath 位置，返回本地 Path。"""
    rel = local_relpath(url)
    target = (dest_root / rel).resolve()
    target = _enforce_within(dest_root, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(target, "wb") as fh:
        fh.write(resp.read())
    return target


def _enforce_within(root: Path, target: Path) -> Path:
    if root.resolve() not in target.resolve().parents:
        raise ValueError(f"安全限制：相对路径越界 {target}")
    return target


def rewrite_html_assets(html: str, url_to_local: dict[str, str], base_url: str) -> str:
    """把 HTML 中已知资源（attr / url() / srcset）的绝对 URL 改写为本地相对路径。"""

    def repl_attr(match: re.Match[str]) -> str:
        attr, quote, value = match.group(1), match.group(2), match.group(3)
        abs_url = urllib.parse.urljoin(base_url, _html.unescape(value))
        local = url_to_local.get(abs_url)
        if local:
            return f"{attr}={quote}{local}{quote}"
        return match.group(0)

    def repl_url(match: re.Match[str]) -> str:
        quote, value = match.group(1), match.group(2)
        abs_url = urllib.parse.urljoin(base_url, _html.unescape(value))
        local = url_to_local.get(abs_url)
        if local:
            return f"url({quote}{local}{quote})"
        return match.group(0)

    def repl_srcset(match: re.Match[str]) -> str:
        quote, value = match.group(2), match.group(3)

        def repl_one(part: str) -> str:
            part = part.strip()
            if not part:
                return ""
            pieces = part.split(None, 1)
            url = pieces[0]
            desc = pieces[1] if len(pieces) > 1 else ""
            abs_url = urllib.parse.urljoin(base_url, _html.unescape(url))
            local = url_to_local.get(abs_url)
            new = local if local else url
            return new + ((" " + desc) if desc else "")

        parts = [repl_one(p) for p in value.split(",")]
        parts = [p for p in parts if p]
        return f"srcset={quote}{', '.join(parts)}{quote}"

    html = _ATTR_PATTERN.sub(repl_attr, html)
    html = _SRCSET_PATTERN.sub(repl_srcset, html)
    html = _URL_FN_PATTERN.sub(repl_url, html)
    return html


# ---------------------------------------------------------------------------
# 站点级链接工具（P0：多页爬取 + 跨页链接改写）
# ---------------------------------------------------------------------------

def norm_key(url: str) -> str:
    """同域内用于匹配路由的规范化键（去掉 query/fragment、统一去尾部斜杠）。"""
    sp = urllib.parse.urlsplit(url)
    p = sp.path or "/"
    if p != "/" and p.endswith("/"):
        p = p[:-1]
    return p


def page_relpath(url: str) -> str:
    """把页面 URL 映射为本地 HTML 相对路径（无后缀自动补 .html，首页为 index.html）。"""
    sp = urllib.parse.urlsplit(url)
    p = sp.path.lstrip("/")
    if p == "" or p.endswith("/"):
        p = (p or "") + "index.html"
    elif not posixpath.splitext(p)[1]:
        p = p + ".html"
    safe = re.sub(r"[^\w\-./]", "_", p)
    return safe.lstrip("./")


def relative_from(current_rel: str, target_rel: str) -> str:
    """从当前页面相对位置计算到目标页面的相对链接（POSIX 风格 / 分隔）。"""
    cur_dir = posixpath.dirname(current_rel) or "."
    return posixpath.relpath(target_rel, cur_dir).replace("\\", "/")


def rewrite_page_links(
    html: str, base_url: str, link_map: dict[str, str], current_rel: str
) -> str:
    """把已爬取路由的 <a href> 改写为本地相对路径；外链/未爬取的保持原样。"""
    base_netloc = urllib.parse.urlsplit(base_url).netloc

    def repl_a(match: re.Match[str]) -> str:
        tag = match.group(0)

        def rh(m: re.Match[str]) -> str:
            quote, value = m.group(2), m.group(3)
            raw = _html.unescape(value).strip()
            if raw.startswith(("#", "mailto:", "tel:", "javascript:")):
                return m.group(0)
            abs_url = urllib.parse.urljoin(base_url, raw)
            sp = urllib.parse.urlsplit(abs_url)
            if sp.netloc != base_netloc:
                return m.group(0)
            key = norm_key(abs_url)
            if key in link_map:
                rel = relative_from(current_rel, link_map[key])
                return f"href={quote}{rel}{quote}"
            return m.group(0)

        return _HREF_PATTERN.sub(rh, tag)

    return _A_TAG_PATTERN.sub(repl_a, html)
