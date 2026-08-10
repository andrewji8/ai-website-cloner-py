"""ai-website-cloner 的 Python 抓取/重建工具包。

核心思路（对齐原仓库 /clone-website 技能）：用 Playwright + Chromium 把页面"读出来"——
抓取渲染后的 DOM、多视口全页截图、提取计算样式设计 token、下载并本地化全部资源，
再重构成一个自包含又可再次构建的静态站点。

模块:
  assets.py  资源发现 / 下载 / 地址改写
  tokens.py  设计 token 提取（计算样式 / 颜色 / 字体）
  crawl.py   基于 Playwright 的采集编排
  build.py   本地资源重组与页面重建
  cli.py     命令行入口
"""

from __future__ import annotations

__all__ = ["assets", "tokens", "crawl", "build", "cli"]