"""
V4: Process AI-generated pixel art (already 64x64, transparent bg).
NO color normalization. Just quantize faithfully and output 4bpp.
"""
import os, struct, zlib, numpy as np
from PIL import Image

RAW_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(RAW_DIR), "graphics", "pokemon", "pikachu", "peakychu")
GBA_GREEN = (152, 208, 160)
ICON_BG = (98, 156, 131)

def write_4bpp_png(pixels, palette, filepath):
    h, w = pixels.shape
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 4, 3, 0, 0, 0)
    plte = b"".join(struct.pack("BBB", r, g, b) for r, g, b in palette)
    raw = b""
    for y in range(h):
        raw += b"\x00"
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

def rgba_to_4bpp(img_rgba, bg_color=GBA_GREEN, max_sprite_colors=15):
    """
    Convert RGBA to 4bpp indexed. No color manipulation.
    1. Hard alpha threshold
    2. Collect opaque pixels, quantize to max_sprite_colors
    3. Index 0 = bg_color (transparent)
    """
    w, h = img_rgba.size
    arr = np.array(img_rgba)
    is_bg = arr[:, :, 3] < 128  # transparent pixels

    # Collect only opaque pixel RGB values for quantization
    opaque_mask = ~is_bg
    if not opaque_mask.any():
        # All transparent
        palette = [bg_color] + [(0, 0, 0)] * 15
        return np.zeros((h, w), dtype=np.uint8), palette

    # Create an image of just the opaque pixels on a neutral background
    # Use the image's own average color as composite bg to avoid color bleed
    opaque_rgb = arr[:, :, :3][opaque_mask]
    avg_r = int(opaque_rgb[:, 0].mean())
    avg_g = int(opaque_rgb[:, 1].mean())
    avg_b = int(opaque_rgb[:, 2].mean())

    bg_img = Image.new("RGBA", (w, h), (avg_r, avg_g, avg_b, 255))
    composite = Image.composite(img_rgba, bg_img, img_rgba.split()[3])
    rgb = composite.convert("RGB")

    # Quantize
    quantized = rgb.quantize(colors=max_sprite_colors, method=Image.Quantize.MEDIANCUT)
    q_pal = quantized.getpalette()
    q_arr = np.array(quantized)

    # Build palette: [bg_color, sprite_color_0, sprite_color_1, ...]
    sprite_colors = []
    for i in range(max_sprite_colors):
        sprite_colors.append((q_pal[i * 3], q_pal[i * 3 + 1], q_pal[i * 3 + 2]))

    palette = [bg_color] + sprite_colors
    while len(palette) < 16:
        palette.append((0, 0, 0))
    palette = palette[:16]

    # Remap: quantized indices 0..n-1 -> our indices 1..n, bg -> 0
    result = q_arr.astype(np.uint8) + 1
    result[is_bg] = 0
    result = np.clip(result, 0, 15)

    return result, palette

def quantize_to_fixed(img_rgba, palette, bg_color):
    """Map each pixel to nearest color in a fixed palette."""
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

def shrink_for_canvas(img_rgba, target_w, target_h, ratio=0.85):
    """Shrink a 64x64 sprite to fit in smaller canvas (e.g. 32x32 for icon/overworld)."""
    mw, mh = int(target_w * ratio), int(target_h * ratio)
    # Crop to content first
    bbox = img_rgba.getbbox()
    if bbox:
        cropped = img_rgba.crop(bbox)
    else:
        cropped = img_rgba
    w, h = cropped.size
    s = min(mw / w, mh / h, 1.0)  # don't upscale
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    resized = cropped.resize((nw, nh), Image.LANCZOS)
    # Hard alpha after resize
    arr = np.array(resized)
    arr[:, :, 3] = np.where(arr[:, :, 3] > 128, 255, 0)
    resized = Image.fromarray(arr, "RGBA")
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    canvas.paste(resized, ((target_w - nw) // 2, target_h - nh), resized)
    return canvas

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

    front_raw = Image.open(f"{RAW_DIR}/peackychu-front-transparent.png").convert("RGBA")
    back_raw = Image.open(f"{RAW_DIR}/Peakychu-back-transparent.png").convert("RGBA")
    print(f"Front: {front_raw.size}, Back: {back_raw.size}")

    # === anim_front.png (64x128, 2 frames) ===
    # Frame 1: original, Frame 2: shifted down 2px for squish anim
    f2 = pxshift(front_raw, 0, 2)
    combined = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
    combined.paste(front_raw, (0, 0), front_raw)
    combined.paste(f2, (0, 64), f2)
    px, front_pal = rgba_to_4bpp(combined)
    write_4bpp_png(px, front_pal, f"{OUT_DIR}/anim_front.png")
    print("anim_front.png done")
    print("Palette:")
    for i, c in enumerate(front_pal):
        print(f"  {i:2d}: {c}")

    # === back.png (64x64) ===
    px, back_pal = rgba_to_4bpp(back_raw)
    write_4bpp_png(px, back_pal, f"{OUT_DIR}/back.png")
    print("back.png done")

    # === icon.png (32x64, shared pal0) ===
    icon_pal = load_icon_palette(0)
    f1 = shrink_for_canvas(front_raw, 32, 32, 0.9)
    f2 = pxshift(f1, 0, -1)
    combined = Image.new("RGBA", (32, 64), (0, 0, 0, 0))
    combined.paste(f1, (0, 0), f1)
    combined.paste(f2, (0, 32), f2)
    px = quantize_to_fixed(combined, icon_pal, ICON_BG)
    write_4bpp_png(px, icon_pal, f"{OUT_DIR}/icon.png")
    print("icon.png done")

    # === overworld.png (192x32, 6 frames) ===
    side_raw = Image.open(f"{RAW_DIR}/Peakychu-facing-right-transparent.png").convert("RGBA")
    front_sm = shrink_for_canvas(front_raw, 32, 32, 0.9)
    back_sm = shrink_for_canvas(back_raw, 32, 32, 0.9)
    side_sm = shrink_for_canvas(side_raw, 32, 32, 0.9)
    sheet = Image.new("RGBA", (192, 32), (0, 0, 0, 0))
    frames = [front_sm, pxshift(front_sm, 1, 0), back_sm, pxshift(back_sm, -1, 0),
              side_sm, pxshift(side_sm, 0, -1)]
    for i, fr in enumerate(frames):
        sheet.paste(fr, (i * 32, 0), fr)
    px, ow_pal = rgba_to_4bpp(sheet)
    write_4bpp_png(px, ow_pal, f"{OUT_DIR}/overworld.png")
    print("overworld.png done")

    # === Palette files ===
    gen_pal(front_pal, f"{OUT_DIR}/normal.pal")
    shiny = [front_pal[0]] + [
        (min(255, int(r * 0.9 + 25)), min(255, int(g * 0.8)), min(255, int(b * 1.1)))
        for r, g, b in front_pal[1:]
    ]
    gen_pal(shiny, f"{OUT_DIR}/shiny.pal")
    gen_pal(ow_pal, f"{OUT_DIR}/overworld_normal.pal")
    ow_shiny = [ow_pal[0]] + [
        (min(255, int(r * 0.9 + 25)), min(255, int(g * 0.8)), min(255, int(b * 1.1)))
        for r, g, b in ow_pal[1:]
    ]
    gen_pal(ow_shiny, f"{OUT_DIR}/overworld_shiny.pal")
    Image.new("1", (16, 16), 0).save(f"{OUT_DIR}/footprint.png")

    print("\nDone!")

if __name__ == "__main__":
    main()
