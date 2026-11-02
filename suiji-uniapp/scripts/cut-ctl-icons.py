#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
岁记 · 从 suiji-icons/ctl-v2 的 512 圆角砖图切出「控件内嵌用」透明底图标。

ctl-v2 的 png512 是完整应用图标砖（角色只占画布约 55%，四周是纯色底），
直接塞进控件会出现两个问题：砖的底色和控件语义底色冲突、角色缩到
30px 以下糊成一团。本脚本做三步：
  1. 边界连通泛洪去底色（只删与图边相连的底色，角色内部的腮红/浅色块保留）
  2. 按主体包围盒裁切 + 统一留白，让不同图标的视觉重量一致
  3. 按控件显示尺寸缩放落盘：ctl/{theme}/{显示rpx}/{name}.png
     （px = ceil(rpx × 2.625)：1rpx 最宽机型约 0.6 CSS px，3x 取 3 倍再留余量）

同一图标被多个控件以不同尺寸使用时，在 ICONS 表追加 rpx 即可，
去底/裁切只算一次，各尺寸分别缩放输出。
只读 suiji-icons/，输出全部落在 suiji-uniapp/src/static/icons/ctl/ 新目录。
用法：python scripts/cut-ctl-icons.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "suiji-icons", "ctl-v2", "png512")
OUT = os.path.join(ROOT, "suiji-uniapp", "src", "static", "icons", "ctl")

# 底色判定阈值（三通道绝对差之和），低于此值且与图边连通即视为背景
TOL = 70
# 主体包围盒外扩比例 + 画布统一留白比例
PAD = 0.04
MARGIN = 1.12
# rpx → 物理 px 系数（64rpx → 168px 规格同源）
PX_PER_RPX = 2.625

# 概念图 → 控件显示 rpx 列表（控件接入按需追加条目，重跑脚本即可）
ICONS = {
    "40-ctl-btn-confirm": [48],         # sj-button icon（对勾旗）
    "41-ctl-btn-add": [48],             # sj-button icon（加号旗）
    "42-ctl-tag": [36],                 # sj-tag icon（举类别小牌）
    "43-ctl-tag-filter": [36],          # sj-tag icon（漏斗筛选）
    "45-ctl-avatar": [128],             # sj-avatar 无图无字回落占位（比心自拍）
    "46-ctl-loading": [192],            # sj-loading 缺省动画图（举转奶瓶）
    "48-ctl-clear": [64, 48],           # sj-notify err（64）/ sj-input·sj-search·sj-textarea 清除钮（48）
    "49-ctl-search-voice": [48],        # sj-search 语音钮
    "58-ctl-upload": [96, 48],          # sj-photo-picker 添加位（96）/ baby·parent 头像角标（48）
    "57-ctl-picker": [56],            # sj-picker 头部条前置图标（奶瓶滚轮举小旗）
    "59-ctl-nav-back": [56],          # sj-navbar 返回钮（举左向箭头指示牌）
    "60-ctl-nav-more": [56],          # sj-navbar 更多钮（举三点指示牌）
    "64-ctl-modal-warn": [64, 88],      # sj-notify warn / sj-modal danger 圆底（三角感叹号）
    "66-ctl-modal-ok": [64, 88],        # sj-notify ok / sj-modal ok 圆底（对勾小旗）
    "67-ctl-popup": [56],               # sj-popup 头部条标题图标（掀开小门帘）
    "73-ctl-calendar": [56],            # sj-datetime-picker date 模式头部条图标（举日历牌）
    "65-ctl-modal-info": [88],          # sj-modal info 圆底（对话气泡 i）
    "69-ctl-empty": [128],              # sj-empty 默认主视觉（空奶纸箱张望）
}

# （原 54a/54b-ctl ± 号拆分切图已废弃：sj-number-box 改用 uview 内置 minus/plus
#  语义矢量字形，位图小尺寸下模糊且语义不清，见 components/sj-number-box/sj-number-box.vue）


def border_bg_color(rgb):
    """取四边像素的中位色作为背景色。"""
    h, w, _ = rgb.shape
    edge = np.concatenate([rgb[0], rgb[h - 1], rgb[:, 0], rgb[:, w - 1]])
    return np.median(edge.reshape(-1, 3), axis=0)


def bg_mask(rgb, ref):
    """从图边出发的连通泛洪：只标记「接近底色且与图边相连」的像素。"""
    h, w, _ = rgb.shape
    cand = np.abs(rgb.astype(int) - ref.astype(int)).sum(axis=2) < TOL
    seen = np.zeros((h, w), dtype=bool)
    stack = ([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
             + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y, x] or not cand[y, x]:
            continue
        seen[y, x] = True
        stack.append((x + 1, y))
        stack.append((x - 1, y))
        stack.append((x, y + 1))
        stack.append((x, y - 1))
    return seen


def largest_cc(alpha):
    """只保留最大连通前景块（字形本体），丢弃框内混入的描边/围巾等 disconnected 碎片。"""
    h, w = alpha.shape
    seen = np.zeros((h, w), dtype=bool)
    best, best_n = None, 0
    for y0 in range(h):
        for x0 in range(w):
            if alpha[y0, x0] and not seen[y0, x0]:
                stack = [(x0, y0)]
                seen[y0, x0] = True
                pts = []
                while stack:
                    x, y = stack.pop()
                    pts.append((y, x))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and alpha[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((nx, ny))
                if len(pts) > best_n:
                    best, best_n = pts, len(pts)
    keep = np.zeros((h, w), dtype=bool)
    if best:
        keep[np.array([p[0] for p in best]), np.array([p[1] for p in best])] = True
    return keep


def prepare(src_png, box=None, erode=True, keep_largest=False):
    """去底 + 包围盒裁切 + 统一留白，返回方形 RGBA 画布（不含最终缩放）。
    box：可选 (l, t, r, b) 比例框，先按原图尺寸裁出局部（拆分切图用）再走同一管线。
    erode=False：跳过 1px 收缩（纯字形框无底色描边，收缩会吃掉细线笔画）。
    keep_largest：只保留最大连通块（纯字形框丢弃框内混入的描边碎片）。"""
    im = Image.open(src_png).convert("RGB")
    if box:
        w, h = im.size
        im = im.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))
    rgb = np.array(im)
    removed = bg_mask(rgb, border_bg_color(rgb))
    alpha = np.where(removed, 0, 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")

    # 1px 收缩吃掉抗锯齿残留的底色描边，再微模糊补回柔和边缘
    a = out.split()[3]
    if erode:
        a = a.filter(ImageFilter.MinFilter(3))
    a = a.filter(ImageFilter.GaussianBlur(0.6))
    if keep_largest:
        an = np.array(a)
        an = np.where(largest_cc(an > 127), an, 0).astype(np.uint8)
        a = Image.fromarray(an, "L")
    out.putalpha(a)

    box = a.getbbox()
    x0, y0, x1, y1 = box
    grow = int((x1 - x0) * PAD)
    subject = out.crop((max(0, x0 - grow), max(0, y0 - grow),
                        min(out.width, x1 + grow), min(out.height, y1 + grow)))

    side = int(max(subject.size) * MARGIN)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(subject, ((side - subject.width) // 2, (side - subject.height) // 2), subject)
    return canvas


def emit(ip, name, canvas, rpx_list):
    for rpx in rpx_list:
        px = math.ceil(rpx * PX_PER_RPX)
        dst_dir = os.path.join(OUT, ip, str(rpx))
        os.makedirs(dst_dir, exist_ok=True)
        canvas.resize((px, px), Image.LANCZOS).save(os.path.join(dst_dir, name + ".png"))
        print("%-5s %-22s %3drpx -> %3dpx  %s"
              % (ip, name, rpx, px, os.path.relpath(dst_dir, ROOT)))


def main():
    for ip in ("bear", "duck"):
        for name, rpx_list in ICONS.items():
            emit(ip, name, prepare(os.path.join(SRC, ip, name + ".png")), rpx_list)


if __name__ == "__main__":
    main()
