import os, glob, json
from PIL import Image, ImageDraw

ROOT = "D:/project/traeData/suiji"
VIBE = os.path.join(ROOT, "vibe_images")
OUT = os.path.join(ROOT, "suiji-icons/ctl-v2")
RAIL = os.path.join(OUT, "rail")
SRC = os.path.join(OUT, "src1920")
BIG = 1920
PNG = 512
R_PX = 115  # corner radius measured from existing assets/icons/*.png (115/512 = 22.5%)

# pick the newest generation for each <ip>-<name> key
latest = {}
for f in glob.glob(os.path.join(VIBE, "*-ctl-*.png")):
    b = os.path.basename(f)
    stem = b.split("_")[0]                      # bear-40-ctl-btn-confirm
    if "-ctl-" not in stem:
        continue
    if stem not in latest or os.path.getmtime(f) > os.path.getmtime(latest[stem]):
        latest[stem] = f

manifest = []
missing = []
for stem, src in sorted(latest.items()):
    ip, name = stem.split("-", 1)
    im = Image.open(src).convert("RGB")
    w, h = im.size
    pts = [(8, 8), (w - 9, 8), (8, h - 9), (w // 2, 8), (8, h // 2), (w - 9, h // 2)]
    px = [im.getpixel(p) for p in pts]
    bg = tuple(sorted(c)[len(c) // 2] for c in zip(*px))
    # the generation service bakes a watermark into the bottom-right corner
    im.paste(Image.new("RGB", (int(w * 0.40), int(h * 0.11)), bg), (int(w * 0.60), int(h * 0.89)))
    im = im.resize((BIG, BIG), Image.LANCZOS)

    for d, fn in ((SRC, "src"), (RAIL, "rail")):
        os.makedirs(os.path.join(d, ip), exist_ok=True)
        im.save(os.path.join(d, ip, name + ".jpg"), "JPEG", quality=93)

    small = im.resize((PNG, PNG), Image.LANCZOS)
    mask = Image.new("L", (PNG, PNG), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, PNG - 1, PNG - 1], radius=R_PX, fill=255)
    small.putalpha(mask)
    os.makedirs(os.path.join(OUT, "png512", ip), exist_ok=True)
    small.save(os.path.join(OUT, "png512", ip, name + ".png"))

    manifest.append({"ip": ip, "name": name, "bg": "#%02X%02X%02X" % bg})
    print(ip, name, "#%02X%02X%02X" % bg)

names = sorted({m["name"] for m in manifest})
for ip in ("bear", "duck"):
    for n in names:
        if not any(m["ip"] == ip and m["name"] == n for m in manifest):
            missing.append(ip + "/" + n)

json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf8"),
          ensure_ascii=False, indent=1)
print("\nconcepts:", len(names), " files:", len(manifest))
print("missing:", missing or "none")
