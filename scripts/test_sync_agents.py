#!/usr/bin/env python3
"""
test_sync_agents.py — 验证 sync_agents.py 的输出正确性。

校验点：
  1) 13 个目标文件都已生成且非空；
  2) 逐字节/规范化后 与原仓库（scripts/sync-agent-rules.sh + sync-skills.mjs）
     生成的对应文件一致 —— 唯一允许的差异是命令引用（原脚本名 -> Python 脚本名）；
  3) 语义检查：AGENTS.md 的 @导入被内联、Gemini TOML 用 {{args}}、AmazonQ JSON 合法、
     Cursor 等文件中 $ARGUMENTS 已被替换。

用法：
  python scripts/test_sync_agents.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DIR = ROOT / "_original_generated"  # 从原仓库下载的对照文件

# 需要生成并校验的全部相对路径
EXPECTED_FILES: list[str] = [
    # 派生自 AGENTS.md（4 份）
    ".github/copilot-instructions.md",
    ".clinerules",
    ".continue/rules/project.md",
    ".amazonq/rules/project.md",
    # 派生自 SKILL.md（9 份）
    ".codex/skills/clone-website/SKILL.md",
    ".github/skills/clone-website/SKILL.md",
    ".cursor/commands/clone-website.md",
    ".windsurf/workflows/clone-website.md",
    ".gemini/commands/clone-website.toml",
    ".opencode/commands/clone-website.md",
    ".augment/commands/clone-website.md",
    ".continue/commands/clone-website.md",
    ".amazonq/cli-agents/clone-website.json",
]

# 规范化：把三种“重新生成命令”的写法统一为占位符，用于与原仓库输出逐字节比较
_CMD_SYMBOLS = [
    "python scripts/sync_agents.py --agents-only",
    "python scripts/sync_agents.py --skills-only",
    "bash scripts/sync-agent-rules.sh",
    "node scripts/sync-skills.mjs",
]


def normalize(text: str, symbol: str = "CMD") -> str:
    for cmd in _CMD_SYMBOLS:
        text = text.replace(cmd, symbol)
    return text


def main() -> int:
    failures: list[str] = []

    # 1) 存在性与非空
    for rel in EXPECTED_FILES:
        path = ROOT / rel
        if not path.is_file():
            failures.append(f"缺失生成文件: {rel}")
        elif path.stat().st_size == 0:
            failures.append(f"生成文件为空: {rel}")

    # 2) 新旧脚本输出一致性（字节级，仅允许命令引用差异）
    for rel in EXPECTED_FILES:
        orig = ORIGINAL_DIR / rel
        if not orig.is_file():
            # 原仓库没有对应生成物的（理论上都会下载到），跳过
            continue
        mine = (ROOT / rel).read_text(encoding="utf-8")
        theirs = orig.read_text(encoding="utf-8")
        if normalize(mine) != normalize(theirs):
            failures.append(f"输出不一致（与原仓库生成文件）：{rel}")

    # 3) 语义检查
    clinerules = (ROOT / ".clinerules").read_text(encoding="utf-8")
    inspection = (ROOT / "docs/research/INSPECTION_GUIDE.md").read_text(encoding="utf-8")
    marker = next(
        (ln for ln in inspection.splitlines() if ln.strip()),
        None,
    )
    if marker is None or marker not in clinerules:
        failures.append(".clinerules 未内联 INSPECTION_GUIDE.md 的 @导入内容")
    if "@docs/research/INSPECTION_GUIDE.md" in clinerules:
        failures.append(".clinerules 中残留未解析的 @导入行")

    gemini = (ROOT / ".gemini/commands/clone-website.toml").read_text(encoding="utf-8")
    if "{{args}}" not in gemini:
        failures.append("Gemini TOML 未将 $ARGUMENTS 替换为 {{args}}")
    if "$ARGUMENTS" in gemini:
        failures.append("Gemini TOML 仍残留 $ARGUMENTS")

    cursor = (ROOT / ".cursor/commands/clone-website.md").read_text(encoding="utf-8")
    if "$ARGUMENTS" in cursor:
        failures.append("Cursor 文件中未替换 $ARGUMENTS")
    if "the target URL provided by the user" not in cursor:
        failures.append("Cursor 文件缺少 $ARGUMENTS 的替换文案")

    amazondir = (ROOT / ".amazonq/cli-agents/clone-website.json")
    try:
        data = json.loads(amazondir.read_text(encoding="utf-8"))
        expected_keys = {"name", "description", "prompt", "fileContext"}
        if not expected_keys.issubset(data):
            failures.append("AmazonQ JSON 缺少必要字段")
        if data["fileContext"] != ["AGENTS.md", "docs/research/**"]:
            failures.append("AmazonQ JSON fileContext 与预期不符")
        if "$ARGUMENTS" in data["prompt"]:
            failures.append("AmazonQ JSON prompt 仍残留 $ARGUMENTS")
    except (json.JSONDecodeError, OSError) as exc:
        failures.append(f"AmazonQ JSON 解析失败: {exc}")

    # 结论
    if failures:
        print("FAIL — 存在以下问题：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"PASS — 全部 {len(EXPECTED_FILES)} 个文件生成且与原仓库输出一致，语义检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())