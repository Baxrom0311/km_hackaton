"""PostureAI app ikonkasini yaratish.

Bu skript Pillow yordamida professional ko'rinishli app ikonkasi yaratadi.
Fon: gradient (deep navy → purple), shakl: stilizatsiya qilingan odam silueti.
"""

from pathlib import Path

def generate_icon():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow o'rnatilmagan. `pip install Pillow` ni ishga tushiring.")
        return

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background (circle)
    for i in range(size // 2, 0, -1):
        ratio = i / (size // 2)
        r = int(26 * ratio + 10 * (1 - ratio))
        g = int(5 * ratio + 15 * (1 - ratio))
        b = int(51 * ratio + 30 * (1 - ratio))
        cx, cy = size // 2, size // 2
        draw.ellipse(
            [cx - i, cy - i, cx + i, cy + i],
            fill=(r, g, b, 255),
        )

    # Accent border ring
    border_w = 8
    draw.ellipse(
        [border_w, border_w, size - border_w, size - border_w],
        outline=(0, 245, 212, 255),
        width=border_w,
    )

    # Stilizatsiya qilingan odam silueti (markazda)
    cx, cy = size // 2, size // 2

    # Bosh (doira)
    head_r = 38
    draw.ellipse(
        [cx - head_r, cy - 110 - head_r, cx + head_r, cy - 110 + head_r],
        fill=(0, 245, 212, 255),
    )

    # Bo'yin + tana
    draw.line([(cx, cy - 72), (cx, cy + 40)], fill=(0, 245, 212, 255), width=12)

    # Yelkalar
    draw.line([(cx - 70, cy - 40), (cx + 70, cy - 40)], fill=(0, 245, 212, 255), width=12)

    # Qo'llar (pastga)
    draw.line([(cx - 70, cy - 40), (cx - 80, cy + 30)], fill=(0, 245, 212, 255), width=10)
    draw.line([(cx + 70, cy - 40), (cx + 80, cy + 30)], fill=(0, 245, 212, 255), width=10)

    # Check mark (to'g'ri posture belgisi)
    check_cx, check_cy = cx + 80, cy + 80
    draw.line(
        [(check_cx - 25, check_cy), (check_cx - 5, check_cy + 20), (check_cx + 30, check_cy - 25)],
        fill=(0, 245, 212, 255),
        width=10,
    )

    # "AI" text (purple accent)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", 48)
        except (OSError, IOError):
            font = ImageFont.load_default()

    draw.text(
        (cx - 28, cy + 100),
        "AI",
        fill=(123, 97, 255, 255),
        font=font,
    )

    # Save PNG
    assets_dir = Path("assets")
    assets_dir.mkdir(exist_ok=True)

    png_path = assets_dir / "icon.png"
    img.save(str(png_path), "PNG")
    print(f"PNG icon saqlandi: {png_path}")

    # Save ICO (Windows uchun)
    ico_path = assets_dir / "icon.ico"
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = [img.resize(s, Image.Resampling.LANCZOS) for s in ico_sizes]
    ico_images[0].save(str(ico_path), format="ICO", sizes=ico_sizes, append_images=ico_images[1:])
    print(f"ICO icon saqlandi: {ico_path}")

    # macOS ICNS — PNG dan yaratamiz
    icns_path = assets_dir / "icon.icns"
    # macOS'da iconutil ishlatamiz
    import subprocess, tempfile, sys
    if sys.platform == "darwin":
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                iconset = Path(tmpdir) / "icon.iconset"
                iconset.mkdir()
                for s in [16, 32, 64, 128, 256, 512]:
                    resized = img.resize((s, s), Image.Resampling.LANCZOS)
                    resized.save(str(iconset / f"icon_{s}x{s}.png"))
                    # @2x versiyalar
                    if s <= 256:
                        resized2x = img.resize((s * 2, s * 2), Image.Resampling.LANCZOS)
                        resized2x.save(str(iconset / f"icon_{s}x{s}@2x.png"))
                subprocess.run(
                    ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"ICNS icon saqlandi: {icns_path}")
        except Exception as e:
            print(f"ICNS yaratishda xatolik: {e}")

    print("App icon yaratish tugadi!")


if __name__ == "__main__":
    generate_icon()
