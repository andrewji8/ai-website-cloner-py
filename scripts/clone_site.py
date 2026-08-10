#!/usr/bin/env python3
"""命令行包装：python scripts/clone_site.py <url> [选项]（需可导入 cloner 包）。"""
from __future__ import annotations

import sys
from pathlib import Path

# 把项目根目录加入 sys.path，以便 import cloner
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cloner.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())