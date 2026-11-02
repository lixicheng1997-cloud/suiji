#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
岁记官网 v4 · Logo 资源生成

源文件：icon/app-icon.png（1024x1024，粉橙渐变「岁记」字标）
       icon/app-icon-rounded.svg（squircle 圆角矢量版）

产出（assets/ 下）：
  icon-192.png        导航 / 页脚小尺寸
  icon-512.png        社交分享 og:image
  apple-touch-icon.png  iOS 添加到主屏（180x180，不带透明边）
  favicon-32.png      浏览器标签页
  logo.svg            矢量版（导航用，可无损缩放）
  logo-rounded.svg    圆角矢量版

用法：python tools/build-logo.py
"""
import os
import shutil

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(os.path.dirname(ROOT), "icon")
OUT = os.path.join(ROOT, "assets")

SRC_PNG = os.path.join(SRC_DIR, "app-icon.png")
SRC_SVG = os.path.join(SRC_DIR, "app-icon.svg")
SRC_SVG_ROUNDED = os.path.join(SRC_DIR, "app-icon-rounded.svg")

# 导航用圆角版：squircle 遮罩，与 App 图标视觉一致
SQUIRCLE_RATIO = 0.225  # 圆角半径 / 边长


def rounded_mask(size: int) -> Image.Image:
    """生成 squircle 圆角遮罩（L 模式，255=可见）。"""
    from PIL import ImageDraw

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    r = int(size * SQUIRCLE_RATIO)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=255)
    return mask


def export(src: Image.Image, name: str, size: int, rounded: bool = False) -> None:
    img = src.convert("RGB").resize((size, size), Image.LANCZOS)
    if rounded:
        img.putalpha(rounded_mask(size))
    path = os.path.join(OUT, name)
    if rounded:
        img.save(path, "PNG", optimize=True)
    else:
        img.save(path, "PNG", optimize=True)
    print(f"  ✓ assets/{name}  ({size}x{size}, {os.path.getsize(path):,} B)")


def main() -> None:
    print("生成 Logo 资源：")
    if not os.path.exists(SRC_PNG):
        raise SystemExit(f"源文件不存在：{SRC_PNG}")

    src = Image.open(SRC_PNG)
    print(f"  源图 {src.size[0]}x{src.size[1]} {src.mode}")

    os.makedirs(OUT, exist_ok=True)

    # 方角版本：favicon / og:image / apple-touch
    export(src, "icon-192.png", 192)
    export(src, "icon-512.png", 512)
    export(src, "apple-touch-icon.png", 180)
    export(src, "favicon-32.png", 32)

    # 圆角版本：导航栏 / 页脚 / 下载区
    export(src, "logo-192-rounded.png", 192, rounded=True)

    # 矢量版本：导航用，任意尺寸无损
    for src_svg, out_name in (
        (SRC_SVG_ROUNDED, "logo.svg"),
        (SRC_SVG, "logo-square.svg"),
    ):
        if os.path.exists(src_svg):
            shutil.copy2(src_svg, os.path.join(OUT, out_name))
            print(f"  ✓ assets/{out_name}  (矢量)")

    print("完成。")


if __name__ == "__main__":
    main()
