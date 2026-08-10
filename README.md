# AI Website Cloner — Python 重构版 / Python Refactor

一个把网站逆向工程为自包含静态站点、并管理多 AI 平台指令文件的 Python 工具。
A Python toolset to reverse-engineer any website into a self-contained static site,
and to manage per-platform AI-agent instruction files.

本项目是对开源仓库 [ai-website-cloner-template](https://github.com/andrewji8/ai-website-cloner-template)
（MIT）的 **纯 Python 重构与扩展**。
This is a pure-Python refactor & extension of the MIT-licensed
[ai-website-cloner-template](https://github.com/andrewji8/ai-website-cloner-template).

---

## 一、简介 / Introduction

原仓库本质上是给 AI 编码助手（Claude Code / Cursor / Windsurf / Gemini CLI / Cline 等）看的
"技能/指令"模板：真正抓取网站的工作由 AI Agent + 浏览器 MCP 完成，仓库里唯一的确定性逻辑
是两份"信源扩散"脚本（`sync-agent-rules.sh` Bash + `sync-skills.mjs` Node.js）。

The original repo is essentially a set of skill/instruction templates for AI coding agents;
the only deterministic code in it is two "source-of-truth propagation" scripts written in
Bash and Node.js.

本项目做两件事 (this project does two things)：

1. **重构（Refactor）**：用一个纯 Python 标准库脚本 `scripts/sync_agents.py`
   **等价合并**那两个 Bash/Node 脚本（生成 4 份代理规则 + 9 份平台技能文件），
   不再依赖 bash / node / npm。
   / Merge the two Bash+Node sync scripts into one pure-stdlib Python script with identical output.

2. **扩展（Extension）**：新增基于 **Playwright + Chromium** 的可执行抓取/重建器
   (`cloner/` 包)，把原 `/clone-website` 技能的"侦察 → 提取 → 构建"落地为真正可运行的代码：
   抓取渲染 DOM、多视口截图、提取设计 token、下载并本地化资源、内联 CSS，重生成自包含站点。
   / Add a runnable Playwright + Chromium crawler/rebuilder that captures the rendered DOM,
   screenshots, design tokens, assets, and rebuilds a self-contained static site.

---

## 二、功能特性 / Features

- **纯 Python**：同步脚本仅用标准库；抓取器唯一第三方依赖是 `playwright`。
- **多平台指令同步**：从 `AGENTS.md` 与 `SKILL.md` 两个信源生成 13 个平台专用文件，
  与原仓库逐字节等价（唯一差异是"重新生成命令"的名字）。
- **真实抓取/重建**：Playwright 打开目标页 → 桌面/移动多视口全页截图 → 提取计算样式
  设计 token（颜色/字体/字号/动效库）→ 并行下载资源并本地化 → 改写 URL → 内联 CSS →
  输出自包含 `index.html` + `research/`。
- **健壮性**：并行下载、短超时、资源数量上限、`domcontentloaded` 兜底，可处理大型企业站。

---

## 三、项目结构 / Project Structure

```
AGENTS.md                             # 代理规则唯一信源 / agent-rules source of truth
.claude/skills/clone-website/SKILL.md # 技能唯一信源 / skill source of truth
docs/research/INSPECTION_GUIDE.md     # 被 AGENTS.md 以 @import 引用的文档
cloner/                               # 抓取/重建包 (Playwright)
  assets.py  tokens.py  crawl.py  build.py  cli.py  __init__.py
scripts/
  sync_agents.py         # 等价替换 sync-agent-rules.sh + sync-skills.mjs
  clone_site.py          # CLI：抓取并重建一个网站
  smoke_playwright.py    # 冒烟：Chromium 启动/导航/截图
  test_sync_agents.py    # 校验 13 个同步产物
  test_cloner_imports.py # 校验 cloner 包语法与资产模块
README.md  docs/  LICENSE  requirements.txt  pyproject.toml
_original_generated/  # (git 忽略) 原仓库输出对照物
_clones/              # (git 忽略) 克隆产物输出目录
```

---

## 四、快速开始 / Quick Start

详见 [docs/INSTALL.md](docs/INSTALL.md)（中英双语安装说明）与 [docs/USAGE.md](docs/USAGE.md)。

```bash
# 1) 安装依赖（Python 3.9+）
pip install -r requirements.txt      # 仅 playwright
python -m playwright install chromium

# 2) 同步多平台指令 / sync per-platform instructions
python scripts/sync_agents.py

# 3) 抓取并重建一个网站 / clone & rebuild a site
python scripts/clone_site.py https://example.com
# 预览 / preview
python scripts/clone_site.py https://example.com --serve

# 4) 运行测试 / run tests
python scripts/test_sync_agents.py
python scripts/test_cloner_imports.py
```

> 若本机装有多个 Python，请用安装了 playwright 的解释器显式调用，例如：
> `C:\Programs\Python311\python.exe scripts\clone_site.py <url>`

---

## 五、已知限制 / Known Limitations

- 抓取仅覆盖**单页**（当前实现）；未递归整站爬取。
- 第三方分析/跟踪脚本（GTM、Adobe Analytics 等）通常无法在离线重建中运行，
  重建页面中会保留它们的远程引用。
- 个体会员/登录内容无法抓取（受登录态与 ToS 约束）。
- 失败资源会被跳过并在 `research/manifest.json` 中如实反映；个别响应可能为 0 字节。

---

## 六、合规声明 / Compliance

仅用于你有权复制的站点、学习或迁移自有站点。请遵守目标站点的服务条款与版权规定；
不得用于钓鱼、冒充或任何非法用途。请勿将本工具产出的第三方内容重新发布。
Use only for sites you own or have permission to reproduce, for learning, or migration.
Respect each site's ToS and copyright. Never use for phishing, impersonation, or illegal use.

---

## 七、许可证 / License

MIT。参见 [LICENSE](LICENSE)。/ See [LICENSE](LICENSE).
