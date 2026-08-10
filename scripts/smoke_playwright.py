#!/usr/bin/env python3
"""冒烟测试：确认 Playwright + Chromium 可启动、可导航、可截图。"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    out = Path(__file__).resolve().parent.parent / "_smoke_artifacts"
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto("https://example.com", wait_until="load", timeout=30_000)
        title = page.title()
        h1 = page.query_selector("h1").inner_text() if page.query_selector("h1") else ""
        print(f"[CHROMIUM OK] title = {title!r}")
        print(f"[CHROMIUM OK] h1    = {h1!r}")
        shot = out / "example_hmac_smoke.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"[CHROMIUM OK] screenshot -> {shot}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())