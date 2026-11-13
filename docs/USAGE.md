# 使用说明 / Usage Guide (中 / EN)

## 一、同步多平台指令 / Sync per-platform instructions

以两个"唯一信源"生成各 AI 平台专用文件。**先改信源，再运行脚本。**

```bash
# 默认：同时同步 AGENTS 规则 + SKILL 技能（生成 13 个文件）
python scripts/sync_agents.py

# 只同步 AGENTS.md 派生的 4 份代理规则
python scripts/sync_agents.py --agents-only

# 只同步 SKILL.md 派生的 9 份平台技能
python scripts/sync_agents.py --skills-only

python scripts/sync_agents.py --help
```

对应关系 / Mapping：

| 编辑的信源 / Source | 命令 / Command | 生成的文件 / Outputs |
| --- | --- | --- |
| `AGENTS.md` | `--agents-only` | `.github/copilot-instructions.md`、`.clinerules`、`.continue/rules/project.md`、`.amazonq/rules/project.md` |
| `.claude/skills/clone-website/SKILL.md` | `--skills-only` | 9 份平台命令/技能文件（codex/github/cursor/windsurf/gemini/opencode/augment/continue/amazonq） |

---

## 二、抓取并重建网站 / Clone & rebuild a website

### 单页模式（默认）

```bash
# 基本用法（抓取到 _clones/<host>_<时间戳>/）
python scripts/clone_site.py https://example.com

# 附加移动端/平板视口
python scripts/clone_site.py https://example.com --viewport tablet=768x1024

# 重建后启动本地 HTTP 服务预览（默认自动打开浏览器）
python scripts/clone_site.py https://example.com --serve --port 8000

# 有头模式（调试，可见浏览器）
python scripts/clone_site.py https://example.com --show

# 指定输出目录
python scripts/clone_site.py https://example.com -o out/example
```

### P0 · 站点级多页爬取 / Whole-site crawl

```bash
# 同域 BFS 抓取多页，共享 assets/，跨页 <a> 改写为相对路径
python scripts/clone_site.py https://example.com --site

# 限制爬取页数（默认 25）
python scripts/clone_site.py https://example.com --site --max-pages 10
```

### P2 · 交互状态采集 / Capture interaction states

```bash
# 点击选择器后截图 + 抓 HTML，标签与选择器用 = 分隔（可多次）
python scripts/clone_site.py https://example.com --state "menu=button.header-menu"

# 同时采集多个状态
python scripts/clone_site.py https://example.com \
  --state "menu=ul[class*=menu]" --state "cart=#cart-button"
```

### P1 · 离线验证产物 / Verify the offline build

```bash
# 检查 srcset 本地化、跨页链接、P2 状态、失败资源审计
python scripts/verify_clone.py _clones/<host>_<时间戳>
```

### 产物 / Outputs

| 步骤 | 产物 |
| --- | --- |
| 多视口采集（默认 desktop 1440 + mobile 390） | `screenshot-desktop.png`、`screenshot-mobile.png` |
| 抓取渲染后的 DOM | `index.html` |
| 提取计算样式设计 token | `research/design-tokens.json` |
| 并行下载并本地化资源（图片/CSS/JS/字体/`srcset` 各档）、改写 URL、内联 CSS | `assets/` |
| P0 站点级多页（`--site`） | 按 URL 路径映射的独立 HTML（如 `us/product/x.html`）+ 共享 `assets/` |
| P1 下载失败审计 | `research/download-failures.json` |
| P1 路由数据（`.json`）本地化 | 计入 `assets/` |
| P2 交互状态（`--state`） | `states/state-<label>.png` + `states/state-<label>.html` |
| 生成研究汇总 | `research/manifest.json`、`research/SITE_SPEC.md`、`research/routes.json` |

---

## 三、测试 / Tests

```bash
# 同步产物校验（对比原仓库输出）
python scripts/test_sync_agents.py

# cloner 包语法 + P0/P1/P2 资产/构建函数冒烟
python scripts/test_cloner_imports.py

# Chromium 启动/导航/截图冒烟
python scripts/smoke_playwright.py
```

---

## 四、实测示例 / Verified examples

- `https://example.com`：0 外部资源，设计 token 精确（黑字 / `#336699` 链接 / `Times New Roman` / 16、24px），重建 `index.html` 经本地服务返回 HTTP 200。
- `https://www.juniper.net/`：大型 AEM 企业站，发现 274 资源、成功本地化 145 个，重建 `index.html` 867KB、内联 10 段 CSS、393 处本地引用；本地服务返回 HTTP 200，标题正确捕获。
- `https://www.lilysilk.com/`（`--site`）：`srcset` 属性 205 处、其中 1845 个响应式档位 URL 被本地化；`img.lilysilk.com` 防盗链对直连 urllib 返回 403/404，全部如实记录于 `research/download-failures.json`。
- `http://quotes.toscrape.com/`（`--site --max-pages 4`）：同域 BFS 抓 4 页，47 条链接中 4 条已爬路由改写为本地相对路径，未爬的保留绝对路径。

---

## 五、合规 / Compliance

仅用于你有权复制的站点。请遵守各站 ToS 与版权；勿用于钓鱼/冒充/非法用途。
Use only for sites you own or have permission to copy. Respect ToS & copyright.
