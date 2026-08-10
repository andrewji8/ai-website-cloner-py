"""在浏览器内提取设计 token：颜色、字体、字号、交互库等。"""
from __future__ import annotations

# 传给 page.evaluate 的脚本：遍历所有元素，汇总计算样式与资源。
JS_TOKENS = r"""
(() => {
  const out = {
    colors: [],
    fontFamilies: [],
    fontSizes: [],
    interactions: {},
    elementCount: 0,
  };
  const add = (arr, v) => { if (v && !arr.includes(v)) arr.push(v); };

  // 收集元素计算样式
  for (const el of document.querySelectorAll('*')) {
    out.elementCount++;
    const st = window.getComputedStyle(el);
    add(out.colors, st.color);
    add(out.colors, st.backgroundColor);
    add(out.fontFamilies, st.fontFamily);
    add(out.fontSizes, st.fontSize);
  }

  // 交互 / 动效库探测
  const fonts = document.fonts ? [...document.fonts].map(f => f.family) : [];
  out.interactions.smoothScroll = !!document.querySelector('.lenis, [data-lenis], html.lenis');
  out.interactions.locomotive = !!document.querySelector('html.has-scroll-init, [data-scroll-container]');
  out.interactions.animations = document.getAnimations ? document.getAnimations().length : 0;
  out.interactions.scrollBehavior = getComputedStyle(document.documentElement).scrollBehavior;
  out.interactions.fonts = [...new Set(fonts)].slice(0, 50);

  out.viewport = { w: window.innerWidth, h: window.innerHeight };
  out.finalUrl = location.href;
  return out;
})()
"""


def extract_tokens(page) -> dict:
    """在已加载的 Playwright page 上执行 JS，返回设计 token 字典。"""
    return page.evaluate(JS_TOKENS)


def summarize_tokens(tokens: dict) -> dict:
    """裁剪成人类可读的精简摘要（限量）。"""
    return {
        "viewport": tokens.get("viewport"),
        "finalUrl": tokens.get("finalUrl"),
        "elementCount": tokens.get("elementCount"),
        "colors": sorted(tokens.get("colors", []))[:30],
        "fontFamilies": sorted(set(tokens.get("fontFamilies", [])))[:20],
        "fontSizes": sorted(
            {float(s.rstrip("px")) for s in tokens.get("fontSizes", []) if s.endswith("px")}
        )[:40],
        "interactions": tokens.get("interactions", {}),
    }