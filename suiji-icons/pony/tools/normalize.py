#!/usr/bin/env python3
"""pony 图标后处理：去白底 → 透明 → 统一画布尺寸 → 导出 PNG / APNG。

单图：  python normalize.py --src raw/01-feeding.png --out 1024 --canvas 1024 --content 880
成组：  python normalize.py --group raw/tab/*.png --out tab-anim/frames --canvas 512 --content 430
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image, ImageFilter

SAT_LIMIT = 30      # 灰阶判定：饱和度低于此值视为水印/底噪


def split_components(img, cells=2, small=256):
    """按连通域把 2x2 四格图拆成独立单帧：主体不会被格子边切到。
    返回按“左上→右上→左下→右下”阅读顺序排列的 4 张 RGBA 图。"""
    w, h = img.size
    a = np.array(img)[:, :, 3] > 12
    low = np.array(img.resize((small, small), Image.NEAREST))[:, :, 3] > 12
    comps = _components(low)
    if not comps:
        raise ValueError("四格图中未识别到任何主体")
    cw, ch = w / cells, h / cells
    anchors = sorted(comps, key=len, reverse=True)[: cells * cells]
    anchor_ids = {id(p) for p in anchors}
    groups = [[] for _ in range(cells * cells)]

    def assign(pts):
        ys = np.array([p[0] for p in pts])
        xs = np.array([p[1] for p in pts])
        step = small / cells
        row = min(int(ys.mean() / step), cells - 1)
        col = min(int(xs.mean() / step), cells - 1)
        return row * cells + col, ys, xs

    for pts in anchors:
        idx, ys, xs = assign(pts)
        groups[idx].append((ys, xs, len(pts)))
    for pts in comps:
        if id(pts) in anchor_ids or len(pts) < 8:
            continue
        idx, ys, xs = assign(pts)
        if groups[idx] and len(pts) < 0.2 * groups[idx][0][2]:
            groups[idx].append((ys, xs, len(pts)))
    out = []
    for g in groups:
        if not g:
            raise ValueError("四格图缺少某一帧")
        keep = np.zeros((small, small), dtype=bool)
        for ys, xs, _ in g:
            keep[ys, xs] = True
        full = np.array(Image.fromarray(keep.astype(np.uint8) * 255).resize((w, h), Image.NEAREST)) > 12
        m = np.array(img).copy()
        m[:, :, 3] = np.where(full & (m[:, :, 3] > 12), m[:, :, 3], 0)
        out.append(Image.fromarray(m, "RGBA"))
    return out


def _components(mask):
    """小区域内 4 邻域连通域标记（纯 Python，区域仅约 150x300 px）。"""
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    comps = []
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            stack = [(sy, sx)]
            seen[sy, sx] = True
            pts = []
            while stack:
                y, x = stack.pop()
                pts.append((y, x))
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            comps.append(pts)
    return comps


def erase_watermark(arr):
    """清掉右下角浅灰水印文字：只删小的灰阶连通笔画，大面积浅色主体（如灰色垃圾桶）保留。"""
    h, w, _ = arr.shape
    y0, x0 = int(h * 0.86), int(w * 0.70)
    box = arr[y0:, x0:]
    mx = box.max(axis=2).astype(np.int16)
    mn = box.min(axis=2).astype(np.int16)
    cand = (mx < 250) & ((mx - mn) < SAT_LIMIT) & (mn > 110)
    if not cand.any():
        return arr, 0
    patch = box.copy()
    wiped = 0
    for pts in _components(cand):
        ys = np.array([p[0] for p in pts])
        xs = np.array([p[1] for p in pts])
        if len(pts) > 3000 or ys.max() - ys.min() > 90 or xs.max() - xs.min() > 260:
            continue  # 疑似主体，保留
        patch[ys, xs] = 255
        wiped += len(pts)
    arr[y0:, x0:] = patch
    return arr, wiped


def background_mask(arr):
    """从四边洪水填充近白区域，保留主体内部的白色块（表盘、奶瓶等）。"""
    h, w, _ = arr.shape
    border = np.concatenate([arr[0, :, :], arr[-1, :, :], arr[:, 0, :], arr[:, -1, :]])
    ref = np.median(border, axis=0)
    dist = np.abs(arr.astype(np.int16) - ref.astype(np.int16)).max(axis=2)
    near = dist <= 26
    bright = arr.min(axis=2) >= 195
    cand = near & bright
    mask = np.zeros((h, w), dtype=bool)
    mask[0, :] = cand[0, :]
    mask[-1, :] = cand[-1, :]
    mask[:, 0] = cand[:, 0]
    mask[:, -1] = cand[:, -1]
    prev = -1
    while mask.sum() != prev:
        prev = mask.sum()
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        mask = grown & cand
    return mask


def to_rgba(arr):
    bg = background_mask(arr)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([arr, alpha]), "RGBA")
    # 边缘羽化 + 去白边（把半透明像素的底色从白底反乘回主体色）
    a = img.split()[3].filter(ImageFilter.GaussianBlur(0.8))
    img.putalpha(a)
    out = np.array(img).astype(np.float32)
    a_n = out[..., 3:4] / 255.0
    safe = np.clip(a_n, 0.08, 1.0)
    out[..., :3] = np.clip((out[..., :3] - 255.0 * (1 - safe)) / safe, 0, 255)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def content_bbox(img):
    a = np.array(img)[:, :, 3]
    ys, xs = np.where(a > 12)
    if len(xs) == 0:
        raise ValueError("全透明，未识别到主体")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def fit(img, canvas, content, box=None, scale=None, anchor="center"):
    x0, y0, x1, y1 = box or content_bbox(img)
    crop = img.crop((x0, y0, x1 + 1, y1 + 1))
    cw, ch = crop.size
    s = scale if scale else content / max(cw, ch)
    crop = crop.resize((max(1, round(cw * s)), max(1, round(ch * s))), Image.LANCZOS)
    sheet = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    left = (canvas - crop.size[0]) // 2
    if anchor == "bottom":
        top = (canvas + content) // 2 - crop.size[1]
    else:
        top = (canvas - crop.size[1]) // 2
    sheet.alpha_composite(crop, (left, top))
    return sheet


def process_single(path, out_dir, canvas, content):
    arr = np.array(Image.open(path).convert("RGB"))
    arr, wiped = erase_watermark(arr)
    rgba = to_rgba(arr)
    final = fit(rgba, canvas, content)
    name = re.split(r"_\d{10,}_", os.path.basename(path))[0]
    name = os.path.splitext(name)[0].replace("pony-raw-", "")
    dst = os.path.join(out_dir, name + ".png")
    final.save(dst)
    print(f"  {name}: 水印像素 {wiped} → {dst} {final.size}")


def process_group(mats, out_dir, canvas, content, base, fps_ms=180, anchor="bottom"):
    """同组帧共用缩放，按底部中心对齐，保证动画不跳位、脚不飘。"""
    boxes = [content_bbox(m) for m in mats]
    biggest = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes) + 1
    scale = content / biggest
    frames = [fit(m, canvas, content, box=b, scale=scale, anchor=anchor) for m, b in zip(mats, boxes)]
    os.makedirs(out_dir, exist_ok=True)
    for i, f in enumerate(frames, 1):
        f.save(os.path.join(out_dir, f"{base}-f{i}.png"))
    apng_dir = os.path.join(os.path.dirname(out_dir), "apng")
    os.makedirs(apng_dir, exist_ok=True)
    frames[0].save(
        os.path.join(apng_dir, base + ".png"),
        save_all=True, append_images=frames[1:], duration=fps_ms, loop=0, disposal=2,
    )
    sheet = Image.new("RGBA", (canvas * len(frames), canvas), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, (canvas * i, 0))
    sprite_dir = os.path.join(os.path.dirname(out_dir), "sprites")
    os.makedirs(sprite_dir, exist_ok=True)
    sheet.save(os.path.join(sprite_dir, base + "-sheet.png"))
    print(f"  {base}: {len(frames)} 帧 → frames/ + apng/ + sprites/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--group", nargs="+")
    ap.add_argument("--grid")
    ap.add_argument("--out", required=True)
    ap.add_argument("--canvas", type=int, default=1024)
    ap.add_argument("--content", type=int, default=880)
    ap.add_argument("--base")
    ap.add_argument("--fps-ms", type=int, default=180)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.grid:
        arr = np.array(Image.open(args.grid).convert("RGB"))
        arr, _ = erase_watermark(arr)
        mats = split_components(to_rgba(arr))
        process_group(mats, args.out, args.canvas, args.content, args.base, args.fps_ms)
    elif args.group:
        paths = sorted(args.group)
        if len(paths) == 1 and os.path.isdir(paths[0]):
            d = paths[0]
            paths = sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".png"))
        mats = []
        for p in paths:
            arr = np.array(Image.open(p).convert("RGB"))
            arr, _ = erase_watermark(arr)
            mats.append(to_rgba(arr))
        process_group(mats, args.out, args.canvas, args.content, args.base or "anim", args.fps_ms)
    else:
        files = [args.src] if args.src and os.path.isfile(args.src) else sorted(
            os.path.join(args.src, f) for f in os.listdir(args.src) if f.lower().endswith(".png")
        )
        for f in files:
            process_single(f, args.out, args.canvas, args.content)


if __name__ == "__main__":
    main()
