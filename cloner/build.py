"""本地资源重组与自包含页面重建，并产出研究性 JSON。"""
from __future__ import annotations

import concurrent.futures
import json
import re
import urllib.parse
from pathlib import Path

from . import assets as assets_mod
from .crawl import Capture
from .tokens import summarize_tokens

_CSS_LINK = re.compile(
    r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', re.IGNORECASE
)

# 并行下载与安全上限，避免大型站点串行超时或资源失控
DOWNLOAD_TIMEOUT = 12          # 单个资源下载超时（秒）
DOWNLOAD_WORKERS = 12          # 并发下载线程数
MAX_ASSETS = 1500              # 单次克隆最多本地化资源数


def _download_all_cross(html: str, base: str, dest_root: Path) -> dict[str, str]:
    """并行下载 HTML 中引用的资源（跨域也下载），返回 URL->本地相对路径。"""
    urls = assets_mod.discover_html_assets(html, base)[:MAX_ASSETS]
    url_to_local: dict[str, str] = {}
    total = len(urls)
    ok = fail = 0
    print(f"    下载资源：共发现 {total} 个，最大并行 {DOWNLOAD_WORKERS}。")

    def _one(u: str):
        local = assets_mod.download(u, dest_root, timeout=DOWNLOAD_TIMEOUT)
        rel = local.relative_to(dest_root).as_posix()
        if not rel.startswith("assets/"):
            rel = f"assets/{rel}"
        return u, rel

    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futs = {pool.submit(_one, u): u for u in urls}
        for i, fut in enumerate(
            concurrent.futures.as_completed(futs), start=1
        ):
            try:
                u, rel = fut.result()
                url_to_local[u] = rel
                ok += 1
            except Exception:
                fail += 1
            if i % 50 == 0 or i == total:
                print(f"    进度：{i}/{total}（成功 {ok}，失败 {fail}）", flush=True)
    return url_to_local


def _inline_remote_css(html: str, url_to_local: dict[str, str], dest_root: Path) -> str:
    """把下载到本地的 <link rel=stylesheet> 内联为 <style>，使页面离线自包含。"""

    def repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        href_m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if not href_m:
            return tag
        original = href_m.group(1)
        local = url_to_local.get(original)
        if not local:
            return tag
        path = dest_root / local.replace("assets/", "", 1)
        try:
            css = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return tag
        return f"<style>\n{css}\n</style>"

    return _CSS_LINK.sub(repl, html)


def rebuild(cap: Capture, out_dir: Path, base_url: str) -> dict:
    """基于采集结果重建自包含静态站点并落盘。"""
    out_dir = Path(out_dir)
    assets_dir = out_dir / "assets"
    research_dir = out_dir / "research"
    assets_dir.mkdir(parents=True, exist_ok=True)
    research_dir.mkdir(parents=True, exist_ok=True)

    html = cap.html
    url_to_local = _download_all_cross(html, base_url, assets_dir)
    html = assets_mod.rewrite_html_assets(html, url_to_local, base_url)
    html = _inline_remote_css(html, url_to_local, assets_dir)

    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")

    # 研究性产物
    summary = summarize_tokens(cap.tokens)
    manifest = {
        "url": base_url,
        "finalUrl": cap.final_url,
        "generatedAt": cap.generated_at,
        "assetsLocalized": len(url_to_local),
        "assets": sorted(url_to_local.values()),
        "designTokens": summary,
    }
    (out_dir / "research" / "design-tokens.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "research" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "research" / "SITE_SPEC.md").write_text(
        _render_spec(summary, manifest), encoding="utf-8"
    )
    return manifest


def _render_spec(tokens: dict, manifest: dict) -> str:
    from urllib.parse import urlsplit

    host = urlsplit(manifest["url"]).netloc or manifest["url"]
    lines = [
        f"# 站点规格 —— {host}",
        "",
        f"- 目标 URL：{manifest['url']}",
        f"- 最终 URL：{manifest['finalUrl']}",
        f"- 生成时间：{manifest['generatedAt']}",
        f"- 本地化资源数：{manifest['assetsLocalized']}",
        "",
        "## 设计 Token",
        "```json",
        json.dumps(tokens, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 说明",
        "本文件由 cloner/ 自动生成，仅供研究参考，请遵守目标站点的服务条款与版权约束。",
        "",
    ]
    return "\n".join(lines)