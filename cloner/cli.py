"""命令行入口：clone_site.py <url> [选项]"""
from __future__ import annotations

import argparse
import http.server
import re
import socketserver
import sys
import webbrowser
from datetime import datetime
from functools import partial
from pathlib import Path

from . import build as build_mod
from .crawl import DEFAULT_VIEWPORTS, capture


def _safe_out_dir(url: str, base: Path) -> Path:
    host = re.sub(r"[^\w.-]", "_", (url.split("//", 1)[-1] if "//" in url else url).split("/")[0])
    return base / f"{host}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _serve(out_dir: Path, port: int, open_browser: bool) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    import contextlib

    with contextlib.closing(socketserver.TCPServer(("", port), handler)) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"[serve] 已启动：{url}")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] 已停止。")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="clone_site.py",
        description="用 Playwright+Chromium 自动抓取并重建一个网站为自包含静态站点。",
    )
    p.add_argument("url", help="目标网址，例如 https://example.com")
    p.add_argument("-o", "--out", default=None, help="输出目录（默认自动生成）")
    p.add_argument(
        "--viewport", action="append", default=None,
        metavar="NAME=WxH", help="附加视口，例如 --viewport tablet=768x1024（可多次）",
    )
    p.add_argument("--headless", action="store_true", default=True, help="无头模式（默认）")
    p.add_argument("--show", action="store_true", help="有头模式（调试）")
    p.add_argument("--serve", action="store_true", help="重建后启动本地 HTTP 服务")
    p.add_argument("--port", type=int, default=8000, help="本地服务端口（默认 8000）")
    p.add_argument("--no-open", action="store_true", help="--serve 时不自动打开浏览器")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.url.startswith(("http://", "https://")):
        print("[err] URL 需以 http(s):// 开头。")
        return 2

    root = Path(__file__).resolve().parent.parent
    base_out = Path(args.out) if args.out else root / "_clones"
    viewports = list(DEFAULT_VIEWPORTS)
    for spec in args.viewport or []:
        try:
            name, dim = spec.split("=", 1)
            w, h = map(int, dim.split("x"))
        except ValueError:
            print(f"[err] 无法解析视口 {spec!r}，应为 NAME=WxH")
            return 2
        viewports.append({"name": name, "width": w, "height": h})

    out_dir = _safe_out_dir(args.url, base_out)
    headless = args.headless and not args.show

    try:
        print(f"[1/3] 采集 {args.url} （chrome={'有头' if not headless else '无头'}）…")
        cap = capture(args.url, out_dir, viewports=viewports, headless=headless)
        print(f"[2/3] 重建到 {out_dir}")
        manifest = build_mod.rebuild(cap, out_dir, args.url)
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        print(f"[err] 抓取/重建失败：{exc}")
        return 1

    print("[3/3] 完成：")
    print(f"  - 截图：{', '.join(cap.screenshots)} → {out_dir}")
    print(f"  - 本地化资源：{manifest['assetsLocalized']} 个")
    print(f"  - 重建页面：{out_dir / 'index.html'}")
    print(f"  - 研究产物：{out_dir / 'research'}")

    if args.serve:
        _serve(out_dir, args.port, not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())