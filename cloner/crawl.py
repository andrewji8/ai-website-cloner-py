"""基于 Playwright 的采集编排：导航、截图、抓渲染 HTML、提取 token、状态、链接。"""
from __future__ import annotations

import posixpath
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import Page, Browser, sync_playwright

from . import tokens as tokens_mod

DEFAULT_VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "mobile", "width": 390, "height": 844},
]

# 浏览器默认 UA（避免被简单反爬识别；仅用于合法学习/自有站点抓取）
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 抓取同域链接用的 JS：返回规范化后的 path（去 query/fragment/尾斜杠），仅同域、可静态解析。
_JS_LINKS = r"""
() => {
  const base = new URL(location.href);
  const out = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    let u;
    try {
      u = new URL(a.getAttribute('href'), location.href);
    } catch (e) { continue; }
    if (u.origin !== base.origin) continue;
    let p = u.pathname;
    if (p !== '/' && p.endsWith('/')) p = p.slice(0, -1);
    out.add(p);
  }
  return [...out];
}
"""


@dataclass
class Capture:
    html: str = ""                    # 桌面视口下的渲染 HTML
    screenshots: dict = field(default_factory=dict)   # {name: 本地路径}
    tokens: dict = field(default_factory=dict)         # 桌面视口 token
    final_url: str = ""
    links: list = field(default_factory=list)          # P0：同域规范化路由（用于 BFS）
    states: dict = field(default_factory=dict)         # P2：{label: {html,path,screenshot}}
    generated_at: str = ""


def _write_screenshot(page: Page, shot_path: Path) -> None:
    shot_path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot_path), full_page=True)


def _new_page(browser: Browser, viewport: dict) -> Page:
    return browser.new_page(viewport=viewport, user_agent=_USER_AGENT)


def capture(
    url: str,
    out_dir,
    viewports=None,
    headless: bool = True,
    states: list[tuple[str, str]] | None = None,
) -> Capture:
    """打开 url，对每个视口截图，抓取渲染 HTML、设计 token、同域链接与交互状态。

    states: P2 可选，形如 [(label, css_selector), ...]；对每个选择器点击并等待后，
            记录该状态下的 HTML 与全页截图。
    """
    viewports = viewports or DEFAULT_VIEWPORTS
    out_dir = Path(out_dir)

    cap = Capture(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = _new_page(browser, {"width": 1440, "height": 900})
        # 大站 load 事件可能迟迟不触发，用 domcontentloaded + 固定等待兜底
        try:
            page.goto(url, wait_until="load", timeout=30_000)
        except Exception:
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(1500)
        cap.final_url = page.url

        # 桌面：抓 HTML + token + 链接
        cap.html = page.evaluate("document.documentElement.outerHTML")
        cap.tokens = tokens_mod.extract_tokens(page)
        try:
            cap.links = page.evaluate(_JS_LINKS)
        except Exception:
            cap.links = []
        base_img = out_dir / "screenshot-desktop.png"
        _write_screenshot(page, base_img)
        cap.screenshots["desktop"] = str(base_img)

        # 其余（含移动端）视口截图
        for vp in viewports:
            key = vp["name"]
            if key == "desktop":
                continue
            page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            page.wait_for_timeout(400)
            shot = out_dir / f"screenshot-{key}.png"
            _write_screenshot(page, shot)
            cap.screenshots[key] = str(shot)

        # P2：交互状态采集（在桌面视口下逐一点选）
        if states:
            page.set_viewport_size({"width": 1440, "height": 900})
            page.wait_for_timeout(300)
            states_dir = out_dir / "states"
            for label, selector in states:
                try:
                    sel = page.locator(selector).first
                    sel.scroll_into_view_if_needed(timeout=3_000)
                    sel.click(timeout=3_000)
                    page.wait_for_timeout(500)
                    state_html = page.evaluate("document.documentElement.outerHTML")
                    shot = states_dir / f"state-{label}.png"
                    _write_screenshot(page, shot)
                    cap.states[label] = {
                        "selector": selector,
                        "html": state_html,
                        "screenshot": str(shot),
                    }
                except Exception as exc:  # noqa: BLE001
                    cap.states[label] = {
                        "selector": selector,
                        "error": f"{type(exc).__name__}: {exc}",
                    }

        browser.close()
    return cap


def discover_same_origin_links(page: Page) -> list[str]:
    """返回当前页同域规范化路由（path，去 query/fragment/尾斜杠），用于站点级 BFS。"""
    try:
        return page.evaluate(_JS_LINKS)
    except Exception:
        return []


def normalize_route(rel_path: str) -> str:
    """把页面内的 path（/a/b）规整为可作目录名的 POSIX 相对路径。"""
    rel = rel_path.strip()
    if rel in ("", "/"):
        return "index.html"
    if rel.startswith("/"):
        rel = rel[1:]
    rel = rel.rstrip("/") or "index.html"
    rel = posixpath.normpath(rel)
    return rel.lstrip("./")
