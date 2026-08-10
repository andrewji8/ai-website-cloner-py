"""资源发现、下载与 HTML 地址改写。"""
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
# CSS 中的 url(...) 引用（内联样式/资源）
_URL_FN_PATTERN = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)

_SKIPPED_EXT = {".ico", ".pem", ".sql", ".map", ".xml", ".json", ".woff2.map"}


def _is_data_uri(value: str) -> bool:
    return value.startswith("data:")


def _is_skip(ext: str) -> bool:
    return ext.lower() in _SKIPPED_EXT or ext == ""


def normalize_url(raw: str, base_url: str) -> str | None:
    """把相对地址解析成绝对 URL；不可用的（data:、空、skip 后缀）返回 None。"""
    raw = raw.strip()
    if not raw or _is_data_uri(raw) or raw.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    url = urllib.parse.urljoin(base_url, raw)
    path = urllib.parse.urlsplit(url).path
    ext = posixpath.splitext(path)[1]
    if _is_skip(ext):
        return None
    return url


def same_origin(url: str, base_url: str) -> bool:
    return urllib.parse.urlsplit(url).netloc == urllib.parse.urlsplit(base_url).netloc


def discover_html_assets(html: str, base_url: str) -> list[str]:
    """从 HTML 文本中找出全部可本地化资源（去重、保序）。"""
    found: set[str] = set()
    ordered: list[str] = []
    for _attr, _quote, value in _ATTR_PATTERN.findall(html):
        url = normalize_url(_html.unescape(value), base_url)
        if url and url not in found:
            found.add(url)
            ordered.append(url)
    for _q, value in _URL_FN_PATTERN.findall(html):
        url = normalize_url(_html.unescape(value), base_url)
        if url and url not in found:
            found.add(url)
            ordered.append(url)
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
    """把 HTML 中已知资源的绝对 URL（按 base_url 解析后）改写为本地相对路径。"""

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

    html = _ATTR_PATTERN.sub(repl_attr, html)
    html = _URL_FN_PATTERN.sub(repl_url, html)
    return html