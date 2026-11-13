#!/usr/bin/env python3
"""快速校验 cloner 包：语法 + 导入 + 单元级资产函数冒烟（含 P0/P1 新增函数）。"""
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

    # --- assets 函数层冒烟（原有） ---
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

    # --- P0: srcset 解析与改写 ---
    srcset_html = (
        '<img src="https://img.example.com/hero.jpg" '
        'srcset="https://img.example.com/hero-320.jpg 320w, '
        'https://img.example.com/hero-640.jpg 640w, '
        'https://img.example.com/hero-1280.jpg 1280w" sizes="100vw">'
    )
    ss_found = assets.discover_html_assets(srcset_html, "https://example.com/")
    expect_ss = [
        "https://img.example.com/hero.jpg",
        "https://img.example.com/hero-320.jpg",
        "https://img.example.com/hero-640.jpg",
        "https://img.example.com/hero-1280.jpg",
    ]
    if ss_found != expect_ss:
        fails.append(f"srcset 发现异常: {ss_found}")
    if assets.parse_srcset("a.png 320w, b.png 640w") != ["a.png", "b.png"]:
        fails.append("parse_srcset 基础解析错误")

    ss_map = {
        "https://img.example.com/hero.jpg": "assets/hero.jpg",
        "https://img.example.com/hero-320.jpg": "assets/hero-320.jpg",
        "https://img.example.com/hero-640.jpg": "assets/hero-640.jpg",
        "https://img.example.com/hero-1280.jpg": "assets/hero-1280.jpg",
    }
    ss_rw = assets.rewrite_html_assets(srcset_html, ss_map, "https://example.com/")
    if "srcset=" not in ss_rw or "assets/hero-320.jpg 320w" not in ss_rw:
        fails.append(f"srcset 改写异常: {ss_rw}")
    if "https://img.example.com" in ss_rw:
        fails.append("srcset 改写后仍残留绝对 URL")

    # P0 回归：srcset 的绝对 URL 不应再被误当普通资源（旧代码会把整串 srcset 值当 URL）
    bogus = [
        u for u in assets.discover_html_assets(srcset_html, "https://example.com/")
        if " 320w" in u or "w, " in u
    ]
    if bogus:
        fails.append(f"srcset 值被当作整体 URL: {bogus}")

    # --- P0: 站点级链接工具 ---
    if assets.norm_key("https://a.com/us/page/?x=1#frag") != "/us/page":
        fails.append(f"norm_key 异常: {assets.norm_key('https://a.com/us/page/?x=1#frag')}")
    if assets.page_relpath("https://a.com/") != "index.html":
        fails.append("page_relpath('/') 应为 index.html")
    if assets.page_relpath("https://a.com/us/product/x") != "us/product/x.html":
        fails.append(f"page_relpath 无后缀补 .html 异常: {assets.page_relpath('https://a.com/us/product/x')}")
    if assets.page_relpath("https://a.com/us/c.html") != "us/c.html":
        fails.append(f"page_relpath 有后缀应原样: {assets.page_relpath('https://a.com/us/c.html')}")
    if assets.relative_from("us/product/x.html", "us/c.html") != "../c.html":
        fails.append(f"relative_from 异常: {assets.relative_from('us/product/x.html', 'us/c.html')}")

    link_html = (
        '<a href="/us/page">P</a> <a href="/ext.html">E</a> '
        '<a href="/us/uncrawled">U</a> <a href="https://other.com/x">O</a> '
        '<a href="mailto:a@b.com">M</a>'
    )
    lm = {"/us/page": "us/page.html", "/ext.html": "ext.html"}
    lrw = assets.rewrite_page_links(link_html, "https://a.com/", lm, "index.html")
    if 'href="us/page.html"' not in lrw:
        fails.append(f"rewrite_page_links 未改写同域已爬路由: {lrw}")
    if 'href="ext.html"' not in lrw:
        fails.append(f"rewrite_page_links 未改写 .html 已爬路由: {lrw}")
    if "https://other.com/x" not in lrw or "mailto:a@b.com" not in lrw:
        fails.append(f"rewrite_page_links 误改外链/mailto: {lrw}")
    # 未爬取的 /us/uncrawled 保持原样（它不在 link_map 中）
    if 'href="/us/uncrawled"' not in lrw:
        fails.append(f"未爬取路由应保持原样: {lrw}")

    # --- P1: .json 不再被跳过（仅本地化被直接引用的），.map 仍跳过 ---
    jhtml = '<script src="/data/routes.json"></script><link rel="stylesheet" href="/x.map">'
    jfound = assets.discover_html_assets(jhtml, "https://a.com/")
    if "https://a.com/data/routes.json" not in jfound:
        fails.append(f"P1: .json 应可发现: {jfound}")
    if any(u.endswith(".map") for u in jfound):
        fails.append(f"P1: .map 仍应跳过: {jfound}")

    # --- P0/P1/P2: build 包可导入且关键符号存在 ---
    from cloner import build  # noqa: E402
    for sym in (
        "rebuild", "crawl_site", "DEFAULT_MAX_PAGES",
        "MAX_ASSETS", "DOWNLOAD_WORKERS",
    ):
        if not hasattr(build, sym):
            fails.append(f"build 缺少符号 {sym}")

    # --- P2: crawl.capture 支持 states 参数（签名层） ---
    import inspect
    from cloner import crawl
    sig = inspect.signature(crawl.capture)
    if "states" not in sig.parameters:
        fails.append("crawl.capture 缺少 states 参数")

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS - 语法与 cloner 资产/构建模块冒烟全部通过（含 P0/P1/P2 新增函数）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
