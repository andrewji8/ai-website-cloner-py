#!/usr/bin/env python3
"""离线验证 cloner 产物：srcset 改写、本地资源、链接改写、P2 状态、失败审计。"""
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
index = (root / "index.html").read_text(encoding="utf-8", errors="replace")

ss_attrs = re.findall(r'srcset=(["\'])(.*?)\1', index, re.DOTALL)
print(f"srcset attrs in index.html: {len(ss_attrs)}")
abs_in_ss = 0
local_in_ss = 0
for _q, val in ss_attrs:
    for part in val.split(","):
        u = part.strip().split()[0] if part.strip() else ""
        if u.startswith("http"):
            abs_in_ss += 1
        elif u:
            local_in_ss += 1
print(f"  srcset URLs pointing to remote: {abs_in_ss}")
print(f"  srcset URLs pointing to local:  {local_in_ss}")

# 本地引用的资源文件是否真实存在
local_refs = set()
for attr in re.findall(r'(?:src|href|poster|srcset)=["\']([^"\']+)["\']', index):
    for tok in re.split(r"\s+", attr):
        t = tok.split(" ", 1)[0]
        if t and not t.startswith(("http", "//", "#", "data:", "mailto:", "tel:", "javascript:")):
            local_refs.add(t.split(",")[0].split()[0])
existing = 0
missing = []
for ref in local_refs:
    p = (root / ref).resolve()
    if p.exists() and p.stat().st_size > 0:
        existing += 1
    elif ref.startswith("assets/") or "assets/" in ref:
        missing.append(ref)
print(f"local asset refs: {len(local_refs)} exist: {existing} missing-asset: {len(missing)}")
for m in missing[:8]:
    print(f"   MISSING: {m}")

# 跨页链接改写情况
links = re.findall(r'<a\b[^>]*href=(["\'])(.*?)\1', index, re.DOTALL)
local_link_refs = set()
remote_link_refs = 0
for q, val in links:
    v = val.strip()
    if v.startswith(("http", "//", "#", "mailto:", "tel:", "javascript:")):
        if v.startswith(("http", "//")):
            remote_link_refs += 1
        continue
    local_link_refs.add(v)
present = 0
for ref in local_link_refs:
    if (root / ref.split("#")[0]).resolve().exists():
        present += 1
print(f"<a> local-link refs: {len(local_link_refs)} (resolved on disk: {present}); remote link refs: {remote_link_refs}")

# P2 状态
m = json.loads((root / "research" / "manifest.json").read_text(encoding="utf-8"))
states = m.get("states", {})
print(f"states captured: {len(states)}")
for k, v in states.items():
    print(f"  - {k}: {v.get('error') or v.get('html_path') or 'n/a'}")

# P1 失败审计
df = json.loads((root / "research" / "download-failures.json").read_text(encoding="utf-8"))
by_status = {}
for d in df:
    key = str(d.get("status") or "non-http")
    by_status[key] = by_status.get(key, 0) + 1
print(f"download failures: {len(df)} by-status={by_status}")
