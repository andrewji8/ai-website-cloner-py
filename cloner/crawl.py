"""基于 Playwright 的采集编排：导航、截图、抓渲染 HTML、提取 token。"""
from __future__ import annotations

from dataclasses import dataclass, field

from playwright.sync_api import Page, sync_playwright

from . import tokens as tokens_mod

DEFAULT_VIEWPORTS = [
    {"name": "desktop", "width": 1440, "height": 900},
    {"name": "mobile", "width": 390, "height": 844},
]


@dataclass
class Capture:
    html: str = ""               # 桌面视口下的渲染 HTML
    screenshots: dict = field(default_factory=dict)   # {name: 本地路径字符串}
    tokens: dict = field(default_factory=dict)        # 桌面视口 token
    final_url: str = ""
    generated_at: str = ""


def _write_screenshot(page: Page, shot_path) -> None:
    import pathlib

    pathlib.Path(shot_path).parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot_path), full_page=True)


def capture(url: str, out_dir, viewports=None, headless: bool = True) -> Capture:
    """打开 url，对每个视口截图，抓取渲染 HTML 与设计 token。"""
    viewports = viewports or DEFAULT_VIEWPORTS
    from datetime import datetime, timezone

    cap = Capture(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        # 大站 load 事件可能迟迟不触发，用 domcontentloaded + 固定等待兜底
        try:
            page.goto(url, wait_until="load", timeout=30_000)
        except Exception:
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(1500)
        cap.final_url = page.url

        # 桌面：抓 HTML + token
        cap.html = page.evaluate("document.documentElement.outerHTML")
        cap.tokens = tokens_mod.extract_tokens(page)
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

        browser.close()
    return cap