#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
岁记官网 v4 · 资源构建脚本

用途：
  1. 生成 Android / iOS 下载二维码（assets/qr/）
  2. 从真实 APK 产物复制到 downloads/
  3. 从设计资源库同步应用图标与双主题图标

用法：
  python tools/build-assets.py                 # 使用下方默认配置
  python tools/build-assets.py --base-url https://suiji.example.com

换域名 / 上架后重新生成二维码：
  修改 SITE_BASE_URL 后重跑本脚本即可。
"""
import argparse
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# ---------------------------------------------------------------- 配置区
# 官网部署基址（suiji-server nginx 托管路径，见 suiji-server/nginx/templates/default.conf.template）
SITE_BASE_URL = "http://49.233.77.155:30080/suiji-website"
APP_VERSION = "1.0.0"
APK_NAME = f"suiji-v{APP_VERSION}.apk"

# 真实 APK 产物来源（uniapp 打包输出）
APK_SOURCE = os.path.join(
    os.path.dirname(ROOT), "suiji-uniapp", "dist", "release", "apk",
    "__UNI__06BAE85__20261102152726.apk"
)

# iOS 上架后的 App Store 链接（未上架时二维码指向官网下载区，扫码可见上架说明）
IOS_STORE_URL = f"{SITE_BASE_URL}/#download"
# ---------------------------------------------------------------- 结束

BRAND = "#EF8F3F"
BRAND_DEEP = "#C9702A"
INK = "#463025"


def make_qr(text: str, out_path: str, logo: str = None) -> None:
    """生成带品牌色与中心留白的二维码。"""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=INK, back_color="white").convert("RGB")
    size = img.size[0]

    # 中心叠加品牌色圆点 + 白色内芯（logo 区域留白由 H 级纠错兜底）
    from PIL import Image, ImageDraw
    dot = ImageDraw.Draw(img)
    r = size // 12
    c = size // 2
    dot.ellipse([c - r, c - r, c + r, c + r], fill=BRAND)
    r2 = max(3, r // 2)
    dot.ellipse([c - r2, c - r2, c + r2, c + r2], fill="white")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "PNG")
    print(f"  ✓ 二维码 {os.path.relpath(out_path, ROOT)}  ({size}px)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=SITE_BASE_URL)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    print(f"岁记官网资源构建 · base-url = {base}")

    # 1. APK 产物同步
    apk_out = os.path.join(ROOT, "downloads", APK_NAME)
    if os.path.exists(APK_SOURCE):
        os.makedirs(os.path.dirname(apk_out), exist_ok=True)
        shutil.copy2(APK_SOURCE, apk_out)
        mb = os.path.getsize(apk_out) / 1024 / 1024
        print(f"  ✓ 安装包 downloads/{APK_NAME}  ({mb:.1f} MB)")
    else:
        print(f"  ! 未找到 APK 产物，跳过：{APK_SOURCE}")

    # 2. 二维码
    print("生成下载二维码：")
    # 指向官网落地页 + ?download=apk：Android 浏览器打开后由 site.js 自动触发
    # 安装包下载；微信内打开会提示「在浏览器中打开」（微信拦截 APK 直链）
    make_qr(f"{base}/?download=apk",
            os.path.join(ROOT, "assets", "qr", "android.png"))
    make_qr(IOS_STORE_URL,
            os.path.join(ROOT, "assets", "qr", "ios.png"))

    # 3. 应用图标同步（Logo 资源由 tools/build-logo.py 统一生成）
    logo_script = os.path.join(ROOT, "tools", "build-logo.py")
    if os.path.exists(logo_script):
        print("生成 Logo 资源：")
        import subprocess
        subprocess.run([sys.executable, logo_script], check=False)

    print("完成。")


if __name__ == "__main__":
    main()
