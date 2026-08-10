# 安装说明 / Installation Guide (中 / EN)

## 环境要求 / Requirements

- **Python 3.9+**
- 网络连接（下载 Chromium 与抓取目标站点）
- 操作系统：Windows / macOS / Linux 均可

> 说明：本项目的"同步脚本"仅用 Python 标准库；唯有"抓取/重建"需要 Playwright 与 Chromium。

---

## 一、安装 Python 依赖 / Install Python dependencies

### 方式 A：使用虚拟环境（推荐）/ With a virtualenv (recommended)

```bash
# Windows
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 方式 B：直接安装 / Directly

```bash
pip install -r requirements.txt
# 或 / or 以可编辑模式安装（同时注册 clone-site 命令）
pip install -e .
```

也可 `pip install playwright`（唯一的第三方依赖）。

---

## 二、安装 Chromium / Install Chromium

```bash
python -m playwright install chromium
```

> 说明：
> - 若无法连接 Google 下载源，可设置镜像：
>   `set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright`（Windows）
>   或 `export PLAYWRIGHT_DOWNLOAD_HOST=...`（macOS/Linux）。
> - Linux 服务器如需系统依赖：`python -m playwright install-deps chromium`。

---

## 三、验证安装 / Verify installation

```bash
# 校验 Chromium 可启动 / 导航 / 截图
python scripts/smoke_playwright.py
# 期望输出：CHROMIUM OK ...

# 校验 cloner 包语法与资产模块
python scripts/test_cloner_imports.py
```

---

## 四、多 Python 环境的注意事项 / Multiple-Python caveat

若 `python` 被解析到某个不含 playwright 的虚拟环境或解释器，请显式指定解释器，
例如在本机（Windows）：

```bash
C:\Programs\Python311\python.exe scripts\clone_site.py https://example.com
```

判断方法 / To check which interpreter has playwright：

```bash
where python
python -c "import playwright; print('ok')"
```

---

## 五、常见问题 / Troubleshooting

| 问题 / Issue | 解决 / Solution |
| --- | --- |
| `No module named 'playwright'` | 你用的解释器不对，改用安装了 playwright 的那个；或 `pip install playwright` |
| 下载 Chromium 超时 | 设置 `PLAYWRIGHT_DOWNLOAD_HOST` 镜像后重试 |
| 页面 `goto` 超时 | 已内置 `domcontentloaded` 兜底；很慢的站可多等片刻 |
| 抓取 0 资源 | 目标站无外部资源（如 example.com）属正常 |
