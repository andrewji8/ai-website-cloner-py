#!/usr/bin/env python3
"""
sync_agents.py — 用 Python 重写原仓库的两个同步脚本。

原仓库 (andrewji8/ai-website-cloner-template) 用两种运行时实现同步：
  * scripts/sync-agent-rules.sh  (bash)  —— 以 AGENTS.md 为唯一信源，
    解析其中 "@path/to/file.md" 的导入语法并内联，再生成 4 份平台代理规则文件。
  * scripts/sync-skills.mjs      (node)  —— 以 .claude/skills/clone-website/SKILL.md
    为唯一信源，解析 YAML frontmatter 与正文，再生成 9 份平台命令/技能文件。

本脚本用纯 Python 标准库（无第三方依赖）合并实现两者完全等价的功能，
只需 Python 3 即可运行，不再依赖 bash 与 node 两个运行时。

用法:
  python scripts/sync_agents.py                # 默认同时同步 AGENTS 规则与 SKILL
  python scripts/sync_agents.py --agents-only  # 仅同步 AGENTS.md 派生的规则文件
  python scripts/sync_agents.py --skills-only  # 仅同步 SKILL.md 派生的技能文件
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 项目根目录（本文件位于 <root>/scripts/sync_agents.py）
ROOT = Path(__file__).resolve().parent.parent


# --- 常量 ---------------------------------------------------------------

SHORT_DESC = "Reverse-engineer and clone any website as a pixel-perfect replica"

# 生成文件顶部统一标注“自动生成、勿直接编辑”，并指明重新生成的命令。
AGENT_RULES_HEADER = (
    "<!-- AUTO-GENERATED from AGENTS.md \u2014 do not edit directly.\n"
    "     Run `python scripts/sync_agents.py --agents-only` to regenerate. -->"
)

SKILL_HEADER = (
    "<!-- AUTO-GENERATED from .claude/skills/clone-website/SKILL.md \u2014 do not edit directly.\n"
    "     Run `python scripts/sync_agents.py --skills-only` to regenerate. -->\n\n"
)

# 与源文件完全一致的平台副本（原样复制 SKILL.md，不改动 $ARGUMENTS）
SKILL_RAW_TARGETS: list[str] = [
    ".codex/skills/clone-website/SKILL.md",
    ".github/skills/clone-website/SKILL.md",
]


# ---------------------------------------------------------------------------
# 一、同步 AGENTS.md 派生的代理规则（等价替换 scripts/sync-agent-rules.sh）
# ---------------------------------------------------------------------------

def resolve_imports(source: Path, root: Path) -> str:
    """解析 AGENTS.md 中 "@path/to/file.md" 形式的导入行（Claude Code 语法）。

    导入行会被替换为该文件的实际内容；若文件缺失，则插入一条提示注释。
    末尾的换行会被剥除（与 bash 命令替换 $() 行为一致）。
    """
    parts: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^@(.+)$", line)
        if match:
            import_path = match.group(1)
            resolved = root / import_path
            if resolved.is_file():
                parts.append(resolved.read_text(encoding="utf-8"))
                parts.append("\n")  # 等价于 bash 的 echo ""
            else:
                parts.append(f"<!-- Import not found: {import_path} -->")
                parts.append("\n")
        else:
            parts.append(line)
            parts.append("\n")
    return "".join(parts).rstrip("\n")


def write_file(target: Path, content: str, header: str) -> None:
    """写入带“自动生成”Header 的内容；Header 与内容、内容末尾各留一个空行。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{header}\n\n{content}\n", encoding="utf-8")
    print(f"  \u2713 {target.relative_to(ROOT)}")


def sync_agent_rules(root: Path) -> None:
    """以 AGENTS.md 为信源，生成 4 份平台代理规则文件。"""
    source = root / "AGENTS.md"
    if not source.is_file():
        raise SystemExit(f"Error: AGENTS.md not found at {source}")

    resolved_content = resolve_imports(source, root)

    print("Syncing agent rules from AGENTS.md...")

    # GitHub Copilot Chat
    write_file(root / ".github/copilot-instructions.md", resolved_content, AGENT_RULES_HEADER)
    # Cline / Roo Code
    write_file(root / ".clinerules", resolved_content, AGENT_RULES_HEADER)
    # Continue（带 YAML frontmatter）
    continue_frontmatter = (
        "---\n"
        "description: Project conventions for AI Website Clone Template\n"
        "alwaysApply: true\n"
        "---"
    )
    write_file(
        root / ".continue/rules/project.md",
        f"{continue_frontmatter}\n{resolved_content}",
        AGENT_RULES_HEADER,
    )
    # Amazon Q Developer
    write_file(root / ".amazonq/rules/project.md", resolved_content, AGENT_RULES_HEADER)

    print()
    print("Done. Generated files are committed to the repo but sourced from AGENTS.md.")
    print("Edit AGENTS.md, then re-run to update all agent configs.")


# ---------------------------------------------------------------------------
# 二、同步 SKILL.md 派生的平台技能/命令文件（等价替换 scripts/sync-skills.mjs）
# ---------------------------------------------------------------------------

def no_args(text: str) -> str:
    """Cursor/Windsurf/AmazonQ 等不支持 $ARGUMENTS，替换为固定描述文案。"""
    return text.replace("$ARGUMENTS", "the target URL provided by the user")


def write_skill(root: Path, rel_path: str, content: str) -> None:
    """写入技能文件并打印相对路径。"""
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    print(f"  \u2713 {rel_path}")


def sync_skills(root: Path) -> None:
    """以 .claude/skills/clone-website/SKILL.md 为信源，生成 9 份平台文件。"""
    source = root / ".claude" / "skills" / "clone-website" / "SKILL.md"
    if not source.is_file():
        raise SystemExit(f"Error: Source skill not found at {source}")

    raw = source.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.match(r"^---\n([\s\S]*?)\n---\n([\s\S]*)$", raw)
    if not match:
        raise SystemExit("Error: Could not parse SKILL.md frontmatter")
    body = match.group(2)

    print("Syncing clone-website skill to all platforms...")
    print(f"  Source: {source.relative_to(ROOT)}\n")

    # 1. Codex CLI / 2. GitHub Copilot —— 与源 SKILL.md 格式一致，原样复制
    for rel_path in SKILL_RAW_TARGETS:
        write_skill(root, rel_path, raw)

    # 3. Cursor / 4. Windsurf —— 纯 Markdown，不支持参数替换
    write_skill(root, ".cursor/commands/clone-website.md", SKILL_HEADER + no_args(body))
    write_skill(root, ".windsurf/workflows/clone-website.md", SKILL_HEADER + no_args(body))

    # 5. Gemini CLI —— TOML 格式，参数用 {{args}}
    gemini_body = body.replace("$ARGUMENTS", "{{args}}")
    write_skill(
        root,
        ".gemini/commands/clone-website.toml",
        "# AUTO-GENERATED from .claude/skills/clone-website/SKILL.md\n"
        "# Run `python scripts/sync_agents.py --skills-only` to regenerate.\n\n"
        f'description = "{SHORT_DESC}"\n'
        f'name = "clone-website"\n\n'
        f"prompt = '''\n{gemini_body}\n'''\n",
    )

    # 6. OpenCode —— Markdown + YAML frontmatter，$ARGUMENTS 原生支持
    write_skill(
        root,
        ".opencode/commands/clone-website.md",
        f'---\ndescription: "{SHORT_DESC}"\n---\n{SKILL_HEADER}{body}',
    )

    # 7. Augment Code —— Markdown + YAML frontmatter
    write_skill(
        root,
        ".augment/commands/clone-website.md",
        f'---\ndescription: "{SHORT_DESC}"\nargument-hint: "<url>"\n---\n{SKILL_HEADER}{body}',
    )

    # 8. Continue —— 带 invokable 标志的 prompt 文件
    write_skill(
        root,
        ".continue/commands/clone-website.md",
        f'---\nname: clone-website\ndescription: "{SHORT_DESC}"\ninvokable: true\n---\n{SKILL_HEADER}{body}',
    )

    # 9. Amazon Q —— JSON agent 定义
    agent_json = json.dumps(
        {
            "name": "clone-website",
            "description": SHORT_DESC,
            "prompt": no_args(body),
            "fileContext": ["AGENTS.md", "docs/research/**"],
        },
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    write_skill(root, ".amazonq/cli-agents/clone-website.json", agent_json)

# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Python 版 AI 网站克隆模板同步器（等价替换 sync-agent-rules.sh 与 sync-skills.mjs）"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--agents-only", action="store_true",
        help="仅同步 AGENTS.md 派生的代理规则文件",
    )
    group.add_argument(
        "--skills-only", action="store_true",
        help="仅同步 SKILL.md 派生的平台技能文件",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.skills_only:
        sync_skills(ROOT)
    elif args.agents_only:
        sync_agent_rules(ROOT)
    else:
        sync_agent_rules(ROOT)
        print()
        sync_skills(ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
    print("\nDone! 9 platform command files generated from source skill.")
    continue_frontmatter = (
        "---\n"
        "description: Project conventions for AI Website Clone Template\n"
        "alwaysApply: true\n"
        "---"
    )
    write_file(
        root / ".continue/rules/project.md",
        f"{continue_frontmatter}\n{resolved_content}",
        AGENT_RULES_HEADER,
    )
    # Amazon Q Developer
    write_file(root / ".amazonq/rules/project.md", resolved_content, AGENT_RULES_HEADER)

    print()
    print("Done. Generated files are committed to the repo but sourced from AGENTS.md.")
    print("Edit AGENTS.md, then re-run to update all agent configs.")