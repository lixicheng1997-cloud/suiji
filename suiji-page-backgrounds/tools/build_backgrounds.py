#!/usr/bin/env python3
"""页面背景套图管线：补绘右下角水印 → 归一 1440×2560 → 导出 PNG 母版 + JPG 投放图。

用法：python tools/build_backgrounds.py            # 全量
      python tools/build_backgrounds.py bear      # 只处理某个 IP
"""
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
OUT_PNG = os.path.join(ROOT, "master")
OUT_JPG = os.path.join(ROOT, "app")
TARGET = (1440, 2560)

# 「Qoder AI生成」这行灰字的位置每张图都有小幅偏移，这里是 15 张实测位置的并集外框（相对宽高）。
# 逐像素检测在草地、水面这类纹理上不可靠，所以直接整块重绘这一小条。
WM_BOX = (0.780, 0.943, 1.0, 1.0)


def clean_watermark(arr):
    """竖向镜像（取自矩形正上方）贴合上边接缝，横向镜像（取自正左方）贴合左边接缝，
    两路按到各自接缝的距离反距离加权，四边都不留矩形痕迹。"""
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = (int(w * WM_BOX[0]), int(h * WM_BOX[1]), int(w * WM_BOX[2]), int(h * WM_BOX[3]))
    bh, bw = y1 - y0, x1 - x0

    def gather(rows, cols):
        return arr[np.clip(rows, 0, h - 1), np.clip(cols, 0, w - 1)].astype(np.float32)

    yy, xx = np.mgrid[y0:y1, x0:x1]
    vert = gather(2 * y0 - 1 - yy, xx)              # 上下翻转：上边接缝天然连续
    horz = gather(yy, 2 * x0 - 1 - xx)              # 左右翻转：左边接缝天然连续
    v = (yy - y0) / max(bh - 1, 1)
    u = (xx - x0) / max(bw - 1, 1)
    k_v = np.exp(-v * 3.2)[..., None]
    k_h = np.exp(-u * 3.2)[..., None]
    arr[y0:y1, x0:x1] = np.clip((k_v * vert + k_h * horz) / (k_v + k_h), 0, 255).astype(np.uint8)
    return arr, (x0, y0, x1, y1)


def normalize_name(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"_\d{10,}_[0-9a-f]+$", "", stem)
    stem = stem.replace("kawaii-", "bg-").replace("-v2", "")
    return stem


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    os.makedirs(OUT_PNG, exist_ok=True)
    os.makedirs(OUT_JPG, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(RAW, "*.png")))
    done = 0
    for p in paths:
        name = normalize_name(p)
        if only and only not in name:
            continue
        arr = np.array(Image.open(p).convert("RGB"))
        arr, box = clean_watermark(arr)
        im = Image.fromarray(arr, "RGB").resize(TARGET, Image.LANCZOS)
        im.save(os.path.join(OUT_PNG, name + ".png"), optimize=True)
        im.save(os.path.join(OUT_JPG, name + ".jpg"), quality=88, optimize=True, progressive=True)
        kb = os.path.getsize(os.path.join(OUT_JPG, name + ".jpg")) // 1024
        print(f"  {name}: 补绘 {box[2]-box[0]}x{box[3]-box[1]} → {TARGET[0]}x{TARGET[1]}  JPG {kb}KB")
        done += 1
    print(f"完成 {done} 张")


if __name__ == "__main__":
    main()
