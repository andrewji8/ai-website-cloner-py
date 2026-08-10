#!/usr/bin/env python3
"""快速校验 cloner 包：语法 + 导入 + 单元级资产函数冒烟。"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PY_SOURCES = [
    "cloner/__init__.py",
    "cloner/assets.py",
    "cloner/tokens.py",
    "cloner/crawl.py",
    "cloner/build.py",
    "cloner/cli.py",
    "scripts/clone_site.py",
]


def main() -> int:
    fails: list[str] = []
    for rel in PY_SOURCES:
        ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)

    from cloner import assets  # noqa: E402

    # assets 函数层冒烟
    html = (
        '<img src="/pic.png"><link rel="stylesheet" href="/style.css">'
        '<script src="https://cdn.example.com/app.js"></script>'
    )
    found = assets.discover_html_assets(html, "https://example.com/a/b")
    if found != [
        "https://example.com/pic.png",
        "https://example.com/style.css",
        "https://cdn.example.com/app.js",
    ]:
        fails.append(f"discover_html_assets 结果异常: {found}")
    if not assets.same_origin(found[0], "https://example.com/x"):
        fails.append("same_origin 判断错误")
    if assets.same_origin(found[2], "https://example.com/x"):
        fails.append("跨域 same_origin 判断错误")
    if assets.local_relpath("https://example.com/pics/a.png") != "pics/a.png":
        fails.append(f"local_relpath 异常: {assets.local_relpath('https://example.com/pics/a.png')}")

    rewritten = assets.rewrite_html_assets(
        html, {"https://example.com/pic.png": "assets/pic.png"}, "https://example.com/a"
    )
    if "assets/pic.png" not in rewritten:
        fails.append("rewrite_html_assets 未改写 img")
    if "https://cdn.example.com/app.js" not in rewritten:
        fails.append("rewrite_html_assets 误改了跨域 script（应保留）")

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS - 语法与 cloner 资产模块冒烟全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())