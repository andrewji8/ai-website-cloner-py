"""本地资源重组、自包含页面重建、站点级爬取编排，并产出研究性 JSON。

P0: 站点级多页爬取（同域 BFS，共享 assets/，跨页链接改写为相对路径）
P1: 下载失败/403/404 审计清单（research/download-failures.json）
既有: 并行下载、CSS 内联、设计 token、SITE_SPEC
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import urllib.error
import urllib.parse
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import assets as assets_mod
from . import crawl as crawl_mod
from .crawl import Capture
from .tokens import summarize_tokens

_CSS_LINK = re.compile(
    r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', re.IGNORECASE
)

# 并行下载与安全上限，避免大型站点串行超时或资源失控
DOWNLOAD_TIMEOUT = 12          # 单个资源下载超时（秒）
DOWNLOAD_WORKERS = 12          # 并发下载线程数
MAX_ASSETS = 1500              # 单次克隆最多本地化资源数
DEFAULT_MAX_PAGES = 25         # 站点级爬取默认页面数上限

# BFS 时跳过这些明显不是页面的链接（当作资源而非路由）
_ASSET_PATH_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".css", ".js", ".mjs", ".mp4", ".webm", ".mp3", ".pdf",
    ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot",
}


def _download_all_cross(
    html_texts: list[str], base: str, dest_root: Path, extra_skip: set[str] | None = None
) -> tuple[dict[str, str], list[dict]]:
    """并行下载全部页面引用的资源（跨域也下载，P1 记录失败清单）。

    返回 (url_to_local, failures)。failures 元素: {url, status?, error}。
    """
    urls: list[str] = []
    seen: set[str] = set()
    for html in html_texts:
        for u in assets_mod.discover_html_assets(html, base, extra_skip):
            if u not in seen:
                seen.add(u)
                urls.append(u)
    urls = urls[:MAX_ASSETS]
    dest_root = Path(dest_root).resolve()
    url_to_local: dict[str, str] = {}
    failures: list[dict] = []
    total = len(urls)
    ok = fail = 0
    print(f"    下载资源：共发现 {total} 个，最大并行 {DOWNLOAD_WORKERS}。")

    def _one(u: str):
        try:
            local = assets_mod.download(u, dest_root, timeout=DOWNLOAD_TIMEOUT)
            rel = local.relative_to(dest_root).as_posix()
            if not rel.startswith("assets/"):
                rel = f"assets/{rel}"
            return u, rel, None
        except urllib.error.HTTPError as e:
            return u, None, {"url": u, "status": e.code, "error": f"HTTP {e.code}"}
        except Exception as e:  # noqa: BLE001
            return u, None, {"url": u, "error": f"{type(e).__name__}: {e}"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futs = {pool.submit(_one, u): u for u in urls}
        for i, fut in enumerate(
            concurrent.futures.as_completed(futs), start=1
        ):
            u, rel, err = fut.result()
            if rel:
                url_to_local[u] = rel
                ok += 1
            else:
                failures.append(err)
                fail += 1
            if i % 50 == 0 or i == total:
                print(f"    进度：{i}/{total}（成功 {ok}，失败 {fail}）", flush=True)
    return url_to_local, failures


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


def _rewrite_page(
    html: str, page_url: str, url_to_local: dict[str, str],
    link_map: dict[str, str], current_rel: str, assets_dir: Path,
) -> str:
    """单页改写：资源 URL 本地化 → CSS 内联 → 已爬取路由的 <a> 改写为相对路径。"""
    html = assets_mod.rewrite_html_assets(html, url_to_local, page_url)
    html = _inline_remote_css(html, url_to_local, assets_dir)
    if link_map:
        html = assets_mod.rewrite_page_links(html, page_url, link_map, current_rel)
    return html


def _write_research(
    cap: Capture, out_dir: Path, base_url: str,
    url_to_local: dict[str, str], failures: list[dict],
    routes: dict[str, str], states: dict | None = None,
) -> dict:
    summary = summarize_tokens(cap.tokens)
    manifest = {
        "url": base_url,
        "finalUrl": cap.final_url,
        "generatedAt": cap.generated_at,
        "assetsLocalized": len(url_to_local),
        "assets": sorted(url_to_local.values()),
        "failedAssets": failures,
        "designTokens": summary,
    }
    if routes:
        manifest["routes"] = routes
    if states:
        manifest["states"] = {
            k: {kk: vv for kk, vv in v.items() if kk != "html"}
            for k, v in states.items()
        }
    research_dir = out_dir / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "design-tokens.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (research_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # P1：下载审计清单
    (research_dir / "download-failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if routes:
        (research_dir / "routes.json").write_text(
            json.dumps(routes, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    _render_spec(summary, manifest, research_dir)
    return manifest


def _render_spec(tokens: dict, manifest: dict, research_dir: Path) -> None:
    from urllib.parse import urlsplit

    host = urlsplit(manifest["url"]).netloc or manifest["url"]
    lines = [
        f"# 站点规格 —— {host}",
        "",
        f"- 目标 URL：{manifest['url']}",
        f"- 最终 URL：{manifest.get('finalUrl', manifest['url'])}",
        f"- 生成时间：{manifest['generatedAt']}",
        f"- 本地化资源数：{manifest['assetsLocalized']}",
        f"- 失败资源数：{len(manifest.get('failedAssets', []))}",
        f"- 已爬取页面：{len(manifest.get('routes', {}))}",
        "",
        "## 设计 Token",
        "```json",
        json.dumps(tokens, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 说明",
        "本文件由 cloner/ 自动生成，仅供研究参考，请遵守目标站点的服务条款与版权约束。",
        "失败资源明细见 research/download-failures.json；已爬取路由见 research/routes.json。",
        "",
    ]
    (research_dir / "SITE_SPEC.md").write_text("\n".join(lines), encoding="utf-8")


def _write_state_htmls(
    states: dict, url_to_local: dict[str, str], base_url: str,
    out_dir: Path, assets_dir: Path,
) -> None:
    """P2：把交互状态的 HTML 也做资源本地化后落盘，便于离线查看。"""
    for label, st in states.items():
        if "html" not in st:
            continue
        states_dir = out_dir / "states"
        states_dir.mkdir(parents=True, exist_ok=True)
        st_html = assets_mod.rewrite_html_assets(st["html"], url_to_local, base_url)
        st_html = _inline_remote_css(st_html, url_to_local, assets_dir)
        st_path = states_dir / f"state-{label}.html"
        st_path.write_text(st_html, encoding="utf-8")
        st["html_path"] = f"states/{st_path.name}"


def rebuild(cap: Capture, out_dir: Path, base_url: str) -> dict:
    """单页模式：基于采集结果重建自包含静态站点并落盘（保持旧行为，P1 附审计）。"""
    out_dir = Path(out_dir)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    url_to_local, failures = _download_all_cross([cap.html], base_url, assets_dir)
    html = _rewrite_page(cap.html, base_url, url_to_local, {}, "index.html", assets_dir)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    _write_state_htmls(cap.states, url_to_local, base_url, out_dir, assets_dir)
    return _write_research(cap, out_dir, base_url, url_to_local, failures, {}, cap.states)


# ---------------------------------------------------------------------------
# P0：站点级多页爬取编排（同域 BFS）
# ---------------------------------------------------------------------------

def crawl_site(
    base_url: str,
    out_dir: Path,
    max_pages: int = DEFAULT_MAX_PAGES,
    headless: bool = True,
    states: list[tuple[str, str]] | None = None,
) -> dict:
    """同域 BFS 爬取最多 max_pages 页，共享 assets/，跨页链接改写为相对路径。

    目录布局:
      out_dir/index.html          根路由（当 base_url 路径为 "/"）
      out_dir/<route>.html        其余路由（按 URL 路径映射，如 us/product/x.html）
      out_dir/assets/**           全部本地化资源（共享）
      out_dir/states/            P2 交互状态截图 + HTML（仅首页）
      out_dir/research/**        manifest / design-tokens / routes / 失败审计
    """
    out_dir = Path(out_dir)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sp0 = urllib.parse.urlsplit(base_url)
    base_key = assets_mod.norm_key(base_url)

    queue: deque[str] = deque([base_key])
    seen: set[str] = {base_key}
    routes: dict[str, str] = {}          # norm_key -> 本地相对文件路径
    pages_html: dict[str, str] = {}      # norm_key -> 渲染 HTML
    page_urls: dict[str, str] = {}       # norm_key -> 浏览器最终 URL
    first_cap: Capture | None = None

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        while queue and len(routes) < max_pages:
            key = queue.popleft()
            url = base_url if key == base_key else f"{sp0.scheme}://{sp0.netloc}{key}"
            print(f"  [page {len(routes) + 1}] {url}")
            page = crawl_mod._new_page(browser, {"width": 1440, "height": 900})
            try:
                try:
                    page.goto(url, wait_until="load", timeout=30_000)
                except Exception:
                    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(1200)
                html = page.evaluate("document.documentElement.outerHTML")
                try:
                    links = page.evaluate(crawl_mod._JS_LINKS)
                except Exception:
                    links = []

                file_rel = assets_mod.page_relpath(url)
                routes[key] = file_rel
                pages_html[key] = html
                page_urls[key] = page.url

                # 首页（首个成功页）：截图 + token + P2 状态
                if first_cap is None:
                    shot = out_dir / "screenshot-desktop.png"
                    crawl_mod._write_screenshot(page, shot)
                    mobile_shot = out_dir / "screenshot-mobile.png"
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_timeout(400)
                    crawl_mod._write_screenshot(page, mobile_shot)
                    page.set_viewport_size({"width": 1440, "height": 900})
                    first_cap = Capture(
                        html=html,
                        screenshots={"desktop": str(shot), "mobile": str(mobile_shot)},
                        final_url=page.url,
                        links=links,
                        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    )
                    first_cap.tokens = crawl_mod.tokens_mod.extract_tokens(page)
                    if states:
                        for label, selector in states:
                            try:
                                sel = page.locator(selector).first
                                sel.scroll_into_view_if_needed(timeout=3_000)
                                sel.click(timeout=3_000)
                                page.wait_for_timeout(500)
                                st_html = page.evaluate(
                                    "document.documentElement.outerHTML"
                                )
                                st_shot = out_dir / "states" / f"state-{label}.png"
                                crawl_mod._write_screenshot(page, st_shot)
                                first_cap.states[label] = {
                                    "selector": selector,
                                    "html": st_html,
                                    "screenshot": str(st_shot),
                                }
                            except Exception as exc:  # noqa: BLE001
                                first_cap.states[label] = {
                                    "selector": selector,
                                    "error": f"{type(exc).__name__}: {exc}",
                                }

                # BFS：同域新路由入队（跳过带资源扩展名的 URL）
                for rel_path in links:
                    link_url = f"{sp0.scheme}://{sp0.netloc}{rel_path}"
                    lk = assets_mod.norm_key(link_url)
                    if lk in seen or lk == key:
                        continue
                    lpath = urllib.parse.urlsplit(link_url).path
                    lext = "." + lpath.rsplit(".", 1)[-1].lower() if "." in lpath.rsplit("/", 1)[-1] else ""
                    if lext in _ASSET_PATH_EXTS:
                        continue
                    seen.add(lk)
                    queue.append(lk)
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {url} 加载失败：{exc}")
            finally:
                page.close()

        browser.close()

    if first_cap is None:
        raise RuntimeError("未能加载任何页面，站点爬取失败")

    # P0/P1：全部页面去重资源下载（页面间 .html 链接交给 link_map，不当资源下载）
    url_to_local, failures = _download_all_cross(
        list(pages_html.values()), base_url, assets_dir,
        extra_skip={"html", "htm"},
    )

    # 跨页链接映射 + 逐页改写落盘
    link_map = dict(routes)
    for key, html in pages_html.items():
        page_url = page_urls[key]
        file_rel = routes[key]
        new_html = _rewrite_page(html, page_url, url_to_local, link_map, file_rel, assets_dir)
        target = out_dir / file_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_html, encoding="utf-8")

    _write_state_htmls(first_cap.states, url_to_local, base_url, out_dir, assets_dir)
    manifest = _write_research(
        first_cap, out_dir, base_url, url_to_local, failures, routes,
        first_cap.states,
    )
    return manifest
