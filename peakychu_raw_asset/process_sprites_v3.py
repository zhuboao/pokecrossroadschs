"""
V3: Fix green tint by compositing onto neutral gray instead of GBA green,
and post-process palette to remove any remaining green-tinted colors.
"""
import os, struct, zlib, numpy as np
from PIL import Image

RAW_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(RAW_DIR), "graphics", "pokemon", "pikachu", "peakychu")
GBA_GREEN = (152, 208, 160)
ICON_BG = (98, 156, 131)

def crop_to_content(img):
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img

def fit_in_canvas(img, cw, ch, ratio=0.85):
    mw, mh = int(cw * ratio), int(ch * ratio)
    w, h = img.size
    s = min(mw / w, mh / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    resized = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(resized, ((cw - nw) // 2, ch - nh), resized)
    return canvas

def normalize_colors(img):
    arr = np.array(img, dtype=np.float64)
    mask = arr[:, :, 3] > 128
    if not mask.any():
        return img
    rm = arr[:, :, 0][mask].mean()
    gm = arr[:, :, 1][mask].mean()
    bm = arr[:, :, 2][mask].mean()
    # Target: pale pinkish-white
    tr, tg, tb = 232, 218, 228
    if rm > 0 and gm > 0 and bm > 0:
        arr[:, :, 0] = np.clip(arr[:, :, 0] * tr / rm, 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] * tg / gm, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * tb / bm, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")

def hard_alpha(img, thr=160):
    arr = np.array(img)
    arr[:, :, 3] = np.where(arr[:, :, 3] > thr, 255, 0)
    return Image.fromarray(arr, "RGBA")

def fix_palette_greens(palette):
    """
    For any sprite color where G > R and G > B (greenish),
    clamp G to avg of R and B so it reads as neutral gray/pink.
    """
    fixed = [palette[0]]  # keep index 0 (BG) untouched
    for r, g, b in palette[1:]:
        if g > r and g > b:
            g = (r + b) // 2
        # Extra: if it's still close to GBA green, push it away
        dist_to_green = abs(r - 152) + abs(g - 208) + abs(b - 160)
        if dist_to_green < 80:
            # Make it more pink/gray
            r = min(255, r + 30)
            g = max(0, g - 30)
            b = min(255, b + 20)
        fixed.append((r, g, b))
    return fixed

def rgba_to_indexed_clean(img_rgba, bg_color=GBA_GREEN, n=15):
    """
    Key fix: composite onto NEUTRAL GRAY (not GBA green!) before quantizing.
    This prevents green from bleeding into the palette.
    """
    w, h = img_rgba.size
    arr = np.array(img_rgba)
    is_bg = arr[:, :, 3] < 128

    # Use neutral pinkish-gray as compositing background
    neutral = Image.new("RGBA", (w, h), (220, 215, 220, 255))
    composite = Image.composite(img_rgba, neutral, img_rgba.split()[3])
    rgb = composite.convert("RGB")

    quantized = rgb.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    q_pal = quantized.getpalette()
    q_arr = np.array(quantized)

    # Extract sprite colors
    sprite_colors = []
    for i in range(n):
        sprite_colors.append((q_pal[i * 3], q_pal[i * 3 + 1], q_pal[i * 3 + 2]))

    # Fix any green-tinted colors
    sprite_colors = fix_palette_greens([(0, 0, 0)] + sprite_colors)[1:]

    palette = [bg_color] + sprite_colors
    while len(palette) < 16:
        palette.append((0, 0, 0))
    palette = palette[:16]

    # Remap indices: quantized uses 0..n-1, we shift to 1..n, bg=0
    result = q_arr.astype(np.uint8) + 1
    result[is_bg] = 0
    result = np.clip(result, 0, 15)

    return result, palette

def write_4bpp_png(pixels, palette, filepath):
    h, w = pixels.shape
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 4, 3, 0, 0, 0)
    plte = b"".join(struct.pack("BBB", r, g, b) for r, g, b in palette)
    raw = b""
    for y in range(h):
        raw += b"\x00"  # no filter
        for x in range(0, w, 2):
            hi = pixels[y, x] & 0x0F
            lo = pixels[y, x + 1] & 0x0F if x + 1 < w else 0
            raw += struct.pack("B", (hi << 4) | lo)
    idat = zlib.compress(raw)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"PLTE", plte))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))

def gen_pal(palette, path):
    lines = ["JASC-PAL", "0100", "16"]
    for r, g, b in palette:
        lines.append(f"{r} {g} {b}")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

def load_icon_palette(idx=0):
    path = os.path.join(os.path.dirname(RAW_DIR),
                        f"graphics/pokemon/icon_palettes/pal{idx}.pal")
    colors = []
    with open(path) as f:
        for line in f.readlines()[3:19]:
            p = line.strip().split()
            if len(p) == 3:
                colors.append((int(p[0]), int(p[1]), int(p[2])))
    return colors

def quantize_to_fixed(img_rgba, palette, bg_color):
    w, h = img_rgba.size
    arr = np.array(img_rgba)
    is_bg = arr[:, :, 3] < 128
    bg_img = Image.new("RGBA", (w, h), (*bg_color, 255))
    comp = np.array(Image.composite(img_rgba, bg_img, img_rgba.split()[3]).convert("RGB"), dtype=np.int32)
    pal_arr = np.array(palette, dtype=np.int32)
    result = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            if is_bg[y, x]:
                result[y, x] = 0
            else:
                d = ((pal_arr[:, 0] - comp[y, x, 0]) ** 2 +
                     (pal_arr[:, 1] - comp[y, x, 1]) ** 2 +
                     (pal_arr[:, 2] - comp[y, x, 2]) ** 2)
                result[y, x] = np.argmin(d)
    return result

def prep(path, cw, ch, ratio=0.85):
    raw = Image.open(path).convert("RGBA")
    raw = normalize_colors(raw)
    raw = hard_alpha(raw, 160)
    return fit_in_canvas(crop_to_content(raw), cw, ch, ratio)

def pxshift(img, dx, dy):
    arr = np.array(img)
    s = np.zeros_like(arr)
    sy, ey = max(0, -dy), arr.shape[0] - max(0, dy)
    sx, ex = max(0, -dx), arr.shape[1] - max(0, dx)
    h, w = ey - sy, ex - sx
    s[max(0, dy):max(0, dy) + h, max(0, dx):max(0, dx) + w] = arr[sy:sy + h, sx:sx + w]
    return Image.fromarray(s, "RGBA")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # === Front ===
    f1 = prep(f"{RAW_DIR}/peackychu-front.png", 64, 64, 0.82)
    f2 = pxshift(prep(f"{RAW_DIR}/peackychu-front.png", 64, 64, 0.80), 0, 2)
    combined = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
    combined.paste(f1, (0, 0), f1)
    combined.paste(f2, (0, 64), f2)
    px, front_pal = rgba_to_indexed_clean(combined)
    write_4bpp_png(px, front_pal, f"{OUT_DIR}/anim_front.png")
    print("anim_front.png - palette:")
    for i, c in enumerate(front_pal):
        print(f"  {i:2d}: {c}")

    # === Back ===
    frame = prep(f"{RAW_DIR}/Peakychu-back-transparent.png", 64, 64, 0.85)
    px, back_pal = rgba_to_indexed_clean(frame)
    write_4bpp_png(px, back_pal, f"{OUT_DIR}/back.png")
    print("back.png done")

    # === Icon ===
    icon_pal = load_icon_palette(0)
    f1 = prep(f"{RAW_DIR}/peackychu-front.png", 32, 32, 0.85)
    f2 = pxshift(f1, 0, -1)
    combined = Image.new("RGBA", (32, 64), (0, 0, 0, 0))
    combined.paste(f1, (0, 0), f1)
    combined.paste(f2, (0, 32), f2)
    px = quantize_to_fixed(combined, icon_pal, ICON_BG)
    write_4bpp_png(px, icon_pal, f"{OUT_DIR}/icon.png")
    print("icon.png done")

    # === Overworld ===
    front = prep(f"{RAW_DIR}/peackychu-front.png", 32, 32, 0.88)
    back = prep(f"{RAW_DIR}/Peakychu-back-transparent.png", 32, 32, 0.88)
    side = prep(f"{RAW_DIR}/Peakychu-facing-right-transparent.png", 32, 32, 0.88)
    sheet = Image.new("RGBA", (192, 32), (0, 0, 0, 0))
    frames = [front, pxshift(front, 1, 0), back, pxshift(back, -1, 0), side, pxshift(side, 0, -1)]
    for i, fr in enumerate(frames):
        sheet.paste(fr, (i * 32, 0), fr)
    px, ow_pal = rgba_to_indexed_clean(sheet)
    write_4bpp_png(px, ow_pal, f"{OUT_DIR}/overworld.png")
    print("overworld.png done")

    # === Palette files ===
    gen_pal(front_pal, f"{OUT_DIR}/normal.pal")
    shiny = [front_pal[0]] + [
        (min(255, r), min(255, int(g * 0.85)), min(255, int(b * 1.05)))
        for r, g, b in front_pal[1:]
    ]
    gen_pal(shiny, f"{OUT_DIR}/shiny.pal")
    gen_pal(ow_pal, f"{OUT_DIR}/overworld_normal.pal")
    ow_shiny = [ow_pal[0]] + [
        (min(255, r), min(255, int(g * 0.85)), min(255, int(b * 1.05)))
        for r, g, b in ow_pal[1:]
    ]
    gen_pal(ow_shiny, f"{OUT_DIR}/overworld_shiny.pal")

    # Placeholder footprint
    Image.new("1", (16, 16), 0).save(f"{OUT_DIR}/footprint.png")

    print("\nAll done! No green-tinted colors in palette.")

if __name__ == "__main__":
    main()
