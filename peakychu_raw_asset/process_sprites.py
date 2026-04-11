"""
Process Peakychu raw assets into GBA-compatible 4bpp indexed sprites.

Key requirements:
- 4-bit indexed PNG (bit_depth=4, color_type=3, max 16 palette entries)
- Transparent background = GBA green (152, 208, 160) at palette index 0
- Hard alpha threshold to avoid green edge bleed
- Icon must use shared icon palette (pal0), not custom palette
"""

from PIL import Image, ImageFilter
import numpy as np
import struct
import zlib
import os

RAW_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(RAW_DIR), "graphics", "pokemon", "pikachu", "peakychu")
GBA_GREEN = (152, 208, 160)
ICON_BG = (98, 156, 131)

def crop_to_content(img):
    """Crop RGBA image to its non-transparent bounding box."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img

def fit_in_canvas(img, canvas_w, canvas_h, ratio=0.85):
    """Resize and center image in canvas, aligned to bottom."""
    max_w = int(canvas_w * ratio)
    max_h = int(canvas_h * ratio)
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    x = (canvas_w - new_w) // 2
    y = canvas_h - new_h
    canvas.paste(resized, (x, y), resized)
    return canvas

def normalize_colors(img_rgba):
    """Normalize color temperature to consistent pale pink-white."""
    arr = np.array(img_rgba, dtype=np.float64)
    alpha = arr[:, :, 3]
    mask = alpha > 128
    if not mask.any():
        return img_rgba
    r_mean = arr[:, :, 0][mask].mean()
    g_mean = arr[:, :, 1][mask].mean()
    b_mean = arr[:, :, 2][mask].mean()
    target_r, target_g, target_b = 230, 215, 225
    if r_mean > 0 and g_mean > 0 and b_mean > 0:
        arr[:, :, 0] = np.clip(arr[:, :, 0] * target_r / r_mean, 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] * target_g / g_mean, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * target_b / b_mean, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")

def hard_alpha_threshold(img_rgba, threshold=160):
    """
    Convert semi-transparent pixels to fully opaque or fully transparent.
    This prevents green bleed at edges.
    """
    arr = np.array(img_rgba)
    alpha = arr[:, :, 3]
    # Pixels with alpha > threshold become fully opaque
    arr[:, :, 3] = np.where(alpha > threshold, 255, 0)
    return Image.fromarray(arr, "RGBA")

def rgba_to_gba_indexed(img_rgba, bg_color=GBA_GREEN, num_sprite_colors=15):
    """
    Convert RGBA to indexed image with bg_color at index 0.
    Returns pixel data as numpy array with indices 0..num_sprite_colors.
    """
    w, h = img_rgba.size
    arr = np.array(img_rgba)
    alpha = arr[:, :, 3]
    is_bg = alpha < 128

    # Composite onto bg_color
    bg = Image.new("RGBA", (w, h), (*bg_color, 255))
    composite = Image.composite(img_rgba, bg, img_rgba.split()[3])
    rgb = composite.convert("RGB")

    # Quantize only the non-background pixels
    quantized = rgb.quantize(colors=num_sprite_colors + 1, method=Image.Quantize.MEDIANCUT)
    q_pal = quantized.getpalette()
    q_arr = np.array(quantized)

    # Get palette colors
    all_indices = set(q_arr.flatten())
    pal_colors = {}
    for idx in all_indices:
        pal_colors[idx] = (q_pal[idx*3], q_pal[idx*3+1], q_pal[idx*3+2])

    # Find the index closest to bg_color among background pixels
    def cdist(c1, c2):
        return sum((a-b)**2 for a, b in zip(c1, c2))

    bg_indices = set(q_arr[is_bg].flatten())
    if bg_indices:
        bg_idx = min(bg_indices, key=lambda i: cdist(pal_colors.get(i, (0,0,0)), bg_color))
    else:
        bg_idx = min(pal_colors.keys(), key=lambda i: cdist(pal_colors[i], bg_color))

    # Build new palette: index 0 = bg_color, then sprite colors
    new_palette = [bg_color]
    old_to_new = {bg_idx: 0}
    new_idx = 1
    for old_idx in sorted(pal_colors.keys()):
        if old_idx == bg_idx:
            continue
        old_to_new[old_idx] = new_idx
        new_palette.append(pal_colors[old_idx])
        new_idx += 1

    # Remap pixels
    result = np.zeros_like(q_arr, dtype=np.uint8)
    for old_idx, new_i in old_to_new.items():
        result[q_arr == old_idx] = new_i

    # Force all background pixels to index 0
    result[is_bg] = 0

    # Pad palette to exactly 16 colors
    while len(new_palette) < 16:
        new_palette.append((0, 0, 0))
    new_palette = new_palette[:16]
    # Force first entry to exact bg_color
    new_palette[0] = bg_color

    return result, new_palette

def write_4bpp_png(pixel_data, palette_16, filepath):
    """
    Write a 4-bit indexed PNG manually.
    Pillow doesn't support writing 4-bit PNGs natively.
    """
    h, w = pixel_data.shape

    # Build PNG file
    def make_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', w, h, 4, 3, 0, 0, 0)
    # 4 = bit depth, 3 = indexed color

    # PLTE
    plte_data = b''
    for r, g, b in palette_16:
        plte_data += struct.pack('BBB', r, g, b)

    # IDAT - pack 2 pixels per byte
    raw_rows = b''
    for y in range(h):
        raw_rows += b'\x00'  # filter byte (none)
        row = pixel_data[y]
        for x in range(0, w, 2):
            hi = row[x] & 0x0F
            lo = row[x+1] & 0x0F if x+1 < w else 0
            raw_rows += struct.pack('B', (hi << 4) | lo)

    idat_data = zlib.compress(raw_rows)

    # Write PNG
    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')  # PNG signature
        f.write(make_chunk(b'IHDR', ihdr_data))
        f.write(make_chunk(b'PLTE', plte_data))
        f.write(make_chunk(b'IDAT', idat_data))
        f.write(make_chunk(b'IEND', b''))

def generate_pal_file(palette_16, path):
    """Generate JASC-PAL format palette file."""
    lines = ["JASC-PAL", "0100", "16"]
    for r, g, b in palette_16:
        lines.append(f"{r} {g} {b}")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

def load_icon_palette(pal_index=0):
    """Load shared icon palette."""
    path = os.path.join(os.path.dirname(RAW_DIR),
                        f"graphics/pokemon/icon_palettes/pal{pal_index}.pal")
    colors = []
    with open(path) as f:
        lines = f.readlines()
    for line in lines[3:19]:
        parts = line.strip().split()
        if len(parts) == 3:
            colors.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return colors

def quantize_to_fixed_palette(img_rgba, palette, bg_color):
    """
    Quantize an RGBA image to a fixed palette.
    Maps each pixel to the nearest color in the palette.
    """
    w, h = img_rgba.size
    arr = np.array(img_rgba)
    alpha = arr[:, :, 3]
    is_bg = alpha < 128

    # Composite onto bg_color
    bg = Image.new("RGBA", (w, h), (*bg_color, 255))
    composite = Image.composite(img_rgba, bg, img_rgba.split()[3])
    rgb_arr = np.array(composite.convert("RGB"), dtype=np.int32)

    # Build palette array
    pal_arr = np.array(palette, dtype=np.int32)

    # For each pixel, find nearest palette color
    result = np.zeros((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            if is_bg[y, x]:
                result[y, x] = 0
            else:
                r, g, b = rgb_arr[y, x]
                dists = ((pal_arr[:, 0] - r)**2 +
                         (pal_arr[:, 1] - g)**2 +
                         (pal_arr[:, 2] - b)**2)
                result[y, x] = np.argmin(dists)

    return result

def process_sprite(raw_path, canvas_w, canvas_h, ratio=0.85):
    """Load, normalize, threshold, crop, and fit a raw image."""
    raw = Image.open(raw_path).convert("RGBA")
    raw = normalize_colors(raw)
    raw = hard_alpha_threshold(raw, threshold=160)
    cropped = crop_to_content(raw)
    return fit_in_canvas(cropped, canvas_w, canvas_h, ratio)

def process_front():
    print("Processing anim_front.png...")
    frame1 = process_sprite(os.path.join(RAW_DIR, "peackychu-front.png"), 64, 64, 0.82)
    # Frame 2: slightly smaller for squish animation
    frame2 = process_sprite(os.path.join(RAW_DIR, "peackychu-front.png"), 64, 64, 0.80)
    # Shift frame2 down by 2px
    f2_arr = np.array(frame2)
    shifted = np.zeros_like(f2_arr)
    shifted[2:, :, :] = f2_arr[:-2, :, :]
    frame2 = Image.fromarray(shifted, "RGBA")

    combined = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
    combined.paste(frame1, (0, 0), frame1)
    combined.paste(frame2, (0, 64), frame2)

    pixels, palette = rgba_to_gba_indexed(combined)
    write_4bpp_png(pixels, palette, os.path.join(OUT_DIR, "anim_front.png"))
    print(f"  -> anim_front.png (4bpp)")
    return palette

def process_back():
    print("Processing back.png...")
    frame = process_sprite(os.path.join(RAW_DIR, "Peakychu-back-transparent.png"), 64, 64, 0.85)

    pixels, palette = rgba_to_gba_indexed(frame)
    write_4bpp_png(pixels, palette, os.path.join(OUT_DIR, "back.png"))
    print(f"  -> back.png (4bpp)")
    return palette

def process_icon():
    print("Processing icon.png...")
    icon_palette = load_icon_palette(0)
    icon_bg = icon_palette[0]  # (98, 156, 131)

    raw = Image.open(os.path.join(RAW_DIR, "peackychu-front.png")).convert("RGBA")
    raw = normalize_colors(raw)
    raw = hard_alpha_threshold(raw, threshold=160)
    cropped = crop_to_content(raw)

    frame1 = fit_in_canvas(cropped, 32, 32, 0.85)
    # Frame 2: bounce (shift up 1px)
    frame2_base = fit_in_canvas(cropped, 32, 32, 0.85)
    f2_arr = np.array(frame2_base)
    shifted = np.zeros_like(f2_arr)
    shifted[:-1, :, :] = f2_arr[1:, :, :]
    frame2 = Image.fromarray(shifted, "RGBA")

    combined = Image.new("RGBA", (32, 64), (0, 0, 0, 0))
    combined.paste(frame1, (0, 0), frame1)
    combined.paste(frame2, (0, 32), frame2)

    # Quantize to shared icon palette
    pixels = quantize_to_fixed_palette(combined, icon_palette, icon_bg)
    write_4bpp_png(pixels, icon_palette, os.path.join(OUT_DIR, "icon.png"))
    print(f"  -> icon.png (4bpp, shared pal0)")

def process_overworld():
    """
    Create overworld.png: 192x32 (6 frames of 32x32).
    Frame layout: down1, down2, up1, up2, side1, side2
    down2/up2/side2 are walk cycle frames (slight shift).
    """
    print("Processing overworld.png...")

    front = process_sprite(os.path.join(RAW_DIR, "peackychu-front.png"), 32, 32, 0.88)
    back = process_sprite(os.path.join(RAW_DIR, "Peakychu-back-transparent.png"), 32, 32, 0.88)
    side = process_sprite(os.path.join(RAW_DIR, "Peakychu-facing-right-transparent.png"), 32, 32, 0.88)

    def shift_pixels(img_rgba, dx, dy):
        arr = np.array(img_rgba)
        shifted = np.zeros_like(arr)
        src_y_start = max(0, -dy)
        src_y_end = arr.shape[0] - max(0, dy)
        src_x_start = max(0, -dx)
        src_x_end = arr.shape[1] - max(0, dx)
        dst_y_start = max(0, dy)
        dst_x_start = max(0, dx)
        h = src_y_end - src_y_start
        w = src_x_end - src_x_start
        shifted[dst_y_start:dst_y_start+h, dst_x_start:dst_x_start+w, :] = \
            arr[src_y_start:src_y_start+h, src_x_start:src_x_start+w, :]
        return Image.fromarray(shifted, "RGBA")

    # Walk frames: slight horizontal shift to simulate stepping
    down2 = shift_pixels(front, 1, 0)
    up2 = shift_pixels(back, -1, 0)
    side2 = shift_pixels(side, 0, -1)

    sheet = Image.new("RGBA", (192, 32), (0, 0, 0, 0))
    frames = [front, down2, back, up2, side, side2]
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * 32, 0), frame)

    pixels, palette = rgba_to_gba_indexed(sheet)
    write_4bpp_png(pixels, palette, os.path.join(OUT_DIR, "overworld.png"))
    print(f"  -> overworld.png (4bpp)")
    return palette

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Output: {OUT_DIR}\n")

    front_pal = process_front()
    back_pal = process_back()
    process_icon()
    ow_pal = process_overworld()

    # Palette files
    print("\nGenerating palette files...")
    generate_pal_file(front_pal, os.path.join(OUT_DIR, "normal.pal"))

    # Shiny: shift toward pink/lavender
    shiny_pal = [front_pal[0]]  # keep bg
    for r, g, b in front_pal[1:]:
        shiny_pal.append((min(255, int(r * 1.0)), min(255, int(g * 0.85)), min(255, int(b * 1.05))))
    generate_pal_file(shiny_pal, os.path.join(OUT_DIR, "shiny.pal"))

    generate_pal_file(ow_pal, os.path.join(OUT_DIR, "overworld_normal.pal"))
    # Reuse shiny logic for overworld
    ow_shiny = [ow_pal[0]]
    for r, g, b in ow_pal[1:]:
        ow_shiny.append((min(255, int(r * 1.0)), min(255, int(g * 0.85)), min(255, int(b * 1.05))))
    generate_pal_file(ow_shiny, os.path.join(OUT_DIR, "overworld_shiny.pal"))

    # Placeholder footprint
    footprint = Image.new("1", (16, 16), 0)
    footprint.save(os.path.join(OUT_DIR, "footprint.png"))

    print("\nDone!")

if __name__ == "__main__":
    main()
