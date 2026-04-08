"""
Process Peakychu raw assets into GBA-compatible sprites for pokeemerald-expansion.

Format requirements:
- Indexed PNG, 16 colors max (first color = GBA green transparent bg)
- anim_front.png: 64x128 (2 frames of 64x64 stacked vertically)
- back.png: 64x64
- icon.png: 32x64 (2 frames of 32x32 stacked vertically)
- overworld.png: 192x32 (6 frames of 32x32 side by side)
- normal.pal: JASC-PAL format, 16 colors
"""

from PIL import Image, ImageFilter
import os
import numpy as np
from collections import Counter

RAW_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(RAW_DIR), "graphics", "pokemon", "pikachu", "peakychu")
GBA_GREEN = (152, 208, 160)
NUM_COLORS = 15  # 15 sprite colors + 1 background

def crop_to_content(img):
    """Crop RGBA image to its non-transparent bounding box."""
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox)
    return img

def fit_in_canvas(img, canvas_w, canvas_h, max_sprite_ratio=0.85):
    """Resize image to fit within a canvas, centered at bottom."""
    max_w = int(canvas_w * max_sprite_ratio)
    max_h = int(canvas_h * max_sprite_ratio)

    w, h = img.size
    scale = min(max_w / w, max_h / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    x = (canvas_w - new_w) // 2
    y = canvas_h - new_h  # align to bottom
    canvas.paste(resized, (x, y), resized)
    return canvas

def normalize_colors(img_rgba):
    """
    Normalize the color temperature across the sprite.
    Since the raw images are screenshots with different lighting,
    we adjust them to have a consistent pale white/pink tone.
    """
    arr = np.array(img_rgba, dtype=np.float64)
    alpha = arr[:, :, 3]
    mask = alpha > 128

    if not mask.any():
        return img_rgba

    # Get average color of opaque pixels
    r_mean = arr[:, :, 0][mask].mean()
    g_mean = arr[:, :, 1][mask].mean()
    b_mean = arr[:, :, 2][mask].mean()

    # Target: a consistent pale pinkish-white (matching the front view)
    target_r, target_g, target_b = 230, 215, 225

    # Compute correction factors
    if r_mean > 0 and g_mean > 0 and b_mean > 0:
        fr = target_r / r_mean
        fg = target_g / g_mean
        fb = target_b / b_mean

        arr[:, :, 0] = np.clip(arr[:, :, 0] * fr, 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] * fg, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * fb, 0, 255)

    return Image.fromarray(arr.astype(np.uint8), "RGBA")

def sharpen_for_pixel_art(img_rgba, canvas_size):
    """Apply slight sharpening to help the downscaled image look crisp."""
    if canvas_size <= 32:
        # For very small sprites, use nearest neighbor for a more pixel-art look
        return img_rgba
    return img_rgba.filter(ImageFilter.SHARPEN)

def rgba_to_indexed(img_rgba, num_colors=NUM_COLORS):
    """
    Convert RGBA image to indexed PNG with GBA green background.
    Returns (indexed_image, palette_colors).
    """
    w, h = img_rgba.size

    # Create a version with GBA green background
    bg = Image.new("RGBA", (w, h), (*GBA_GREEN, 255))
    composite = Image.composite(img_rgba, bg, img_rgba.split()[3])

    # Quantize to num_colors+1 (including the green bg)
    rgb = composite.convert("RGB")
    quantized = rgb.quantize(colors=num_colors + 1, method=Image.Quantize.MEDIANCUT)

    # Ensure GBA green is the first palette color
    palette = quantized.getpalette()
    pal_colors = [(palette[i*3], palette[i*3+1], palette[i*3+2]) for i in range(num_colors + 1)]

    # Find the closest color to GBA green in the palette
    def color_dist(c1, c2):
        return sum((a - b) ** 2 for a, b in zip(c1, c2))

    green_idx = min(range(len(pal_colors)), key=lambda i: color_dist(pal_colors[i], GBA_GREEN))

    # Swap green to index 0
    if green_idx != 0:
        pal_colors[0], pal_colors[green_idx] = pal_colors[green_idx], pal_colors[0]
        # Rebuild palette
        new_palette = []
        for c in pal_colors:
            new_palette.extend(c)
        # Pad to 256 entries
        new_palette.extend([0] * (768 - len(new_palette)))

        # Remap pixel data
        px = list(quantized.getdata())
        remap = list(range(256))
        remap[0] = green_idx
        remap[green_idx] = 0
        px = [remap[p] for p in px]

        result = Image.new("P", (w, h))
        result.putdata(px)
        result.putpalette(new_palette)
    else:
        result = quantized
        new_palette = palette

    # Force the first palette color to be exactly GBA green
    final_palette = list(result.getpalette())
    final_palette[0:3] = list(GBA_GREEN)
    result.putpalette(final_palette)

    # Ensure exactly 16 colors in palette
    pal = result.getpalette()
    final_colors = [(pal[i*3], pal[i*3+1], pal[i*3+2]) for i in range(16)]

    return result, final_colors

def generate_pal_file(colors, path):
    """Generate a JASC-PAL format palette file."""
    lines = ["JASC-PAL", "0100", "16"]
    for r, g, b in colors:
        lines.append(f"{r} {g} {b}")
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

def process_front_sprite():
    """Create anim_front.png: 64x128 (2 frames)."""
    print("Processing front sprite...")
    raw = Image.open(os.path.join(RAW_DIR, "peackychu-front.png")).convert("RGBA")
    raw = normalize_colors(raw)
    cropped = crop_to_content(raw)

    # Frame 1: normal pose
    frame1 = fit_in_canvas(cropped, 64, 64, max_sprite_ratio=0.82)
    frame1 = sharpen_for_pixel_art(frame1, 64)

    # Frame 2: slight shift for animation (shift down 2px)
    frame2_inner = fit_in_canvas(cropped, 64, 64, max_sprite_ratio=0.80)
    frame2 = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    frame2.paste(frame2_inner, (0, 2), frame2_inner)

    # Stack frames
    combined = Image.new("RGBA", (64, 128), (0, 0, 0, 0))
    combined.paste(frame1, (0, 0), frame1)
    combined.paste(frame2, (0, 64), frame2)

    indexed, palette = rgba_to_indexed(combined)
    indexed.save(os.path.join(OUT_DIR, "anim_front.png"))
    print(f"  -> anim_front.png saved ({indexed.size})")
    return palette

def process_back_sprite(front_palette=None):
    """Create back.png: 64x64."""
    print("Processing back sprite...")
    raw = Image.open(os.path.join(RAW_DIR, "Peakychu-back-transparent.png")).convert("RGBA")
    raw = normalize_colors(raw)
    cropped = crop_to_content(raw)

    frame = fit_in_canvas(cropped, 64, 64, max_sprite_ratio=0.85)
    frame = sharpen_for_pixel_art(frame, 64)

    indexed, palette = rgba_to_indexed(frame)
    indexed.save(os.path.join(OUT_DIR, "back.png"))
    print(f"  -> back.png saved ({indexed.size})")
    return palette

def process_icon():
    """Create icon.png: 32x64 (2 frames of 32x32)."""
    print("Processing icon sprite...")
    raw = Image.open(os.path.join(RAW_DIR, "peackychu-front.png")).convert("RGBA")
    raw = normalize_colors(raw)
    cropped = crop_to_content(raw)

    # Frame 1
    frame1 = fit_in_canvas(cropped, 32, 32, max_sprite_ratio=0.85)
    # Frame 2: slight bounce (shift up 1px)
    frame2_inner = fit_in_canvas(cropped, 32, 32, max_sprite_ratio=0.85)
    frame2 = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    # Shift content up by 1 pixel for bounce animation
    arr = np.array(frame2_inner)
    shifted = np.zeros_like(arr)
    shifted[:-1, :, :] = arr[1:, :, :]
    frame2 = Image.fromarray(shifted, "RGBA")

    combined = Image.new("RGBA", (32, 64), (0, 0, 0, 0))
    combined.paste(frame1, (0, 0), frame1)
    combined.paste(frame2, (0, 32), frame2)

    indexed, palette = rgba_to_indexed(combined)
    indexed.save(os.path.join(OUT_DIR, "icon.png"))
    print(f"  -> icon.png saved ({indexed.size})")

def process_overworld():
    """
    Create overworld.png: 192x32 (6 frames of 32x32).
    Layout: down1, down2, up1, up2, side1, side2
    Using: front=down, back=up, facing-right=side
    """
    print("Processing overworld sprites...")

    front_raw = Image.open(os.path.join(RAW_DIR, "peackychu-front.png")).convert("RGBA")
    back_raw = Image.open(os.path.join(RAW_DIR, "Peakychu-back-transparent.png")).convert("RGBA")
    side_raw = Image.open(os.path.join(RAW_DIR, "Peakychu-facing-right-transparent.png")).convert("RGBA")

    for img in [front_raw, back_raw, side_raw]:
        normalize_colors(img)

    front_crop = crop_to_content(normalize_colors(front_raw))
    back_crop = crop_to_content(normalize_colors(back_raw))
    side_crop = crop_to_content(normalize_colors(side_raw))

    # Create 6 frames at 32x32
    down1 = fit_in_canvas(front_crop, 32, 32, max_sprite_ratio=0.9)
    # down2: shift 1px for walk cycle
    down2 = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d2_inner = fit_in_canvas(front_crop, 32, 32, max_sprite_ratio=0.9)
    down2.paste(d2_inner, (1, 0), d2_inner)

    up1 = fit_in_canvas(back_crop, 32, 32, max_sprite_ratio=0.9)
    up2 = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    u2_inner = fit_in_canvas(back_crop, 32, 32, max_sprite_ratio=0.9)
    up2.paste(u2_inner, (1, 0), u2_inner)

    side1 = fit_in_canvas(side_crop, 32, 32, max_sprite_ratio=0.9)
    side2 = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    s2_inner = fit_in_canvas(side_crop, 32, 32, max_sprite_ratio=0.9)
    side2.paste(s2_inner, (0, -1), s2_inner)

    # Combine into sprite sheet
    sheet = Image.new("RGBA", (192, 32), (0, 0, 0, 0))
    frames = [down1, down2, up1, up2, side1, side2]
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * 32, 0), frame)

    indexed, palette = rgba_to_indexed(sheet)
    indexed.save(os.path.join(OUT_DIR, "overworld.png"))
    print(f"  -> overworld.png saved ({indexed.size})")
    return palette

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Output directory: {OUT_DIR}")
    print()

    # Process all sprites
    front_palette = process_front_sprite()
    back_palette = process_back_sprite()
    process_icon()
    ow_palette = process_overworld()

    # Generate palette files using front sprite palette
    print("\nGenerating palette files...")
    generate_pal_file(front_palette, os.path.join(OUT_DIR, "normal.pal"))
    print("  -> normal.pal saved")

    # Shiny palette: slightly different tint (more pinkish)
    shiny_colors = []
    for i, (r, g, b) in enumerate(front_palette):
        if i == 0:
            shiny_colors.append((r, g, b))  # keep GBA green
        else:
            # Shift toward a light pink/lavender for shiny
            sr = min(255, int(r * 1.0))
            sg = min(255, int(g * 0.85))
            sb = min(255, int(b * 1.05))
            shiny_colors.append((sr, sg, sb))
    generate_pal_file(shiny_colors, os.path.join(OUT_DIR, "shiny.pal"))
    print("  -> shiny.pal saved")

    # Generate overworld palettes
    generate_pal_file(ow_palette, os.path.join(OUT_DIR, "overworld_normal.pal"))
    print("  -> overworld_normal.pal saved")
    generate_pal_file(shiny_colors, os.path.join(OUT_DIR, "overworld_shiny.pal"))
    print("  -> overworld_shiny.pal saved")

    # Generate footprint (1-bit, 16x16 - use Pikachu's for now)
    # Just create a simple placeholder
    footprint = Image.new("1", (16, 16), 0)
    footprint.save(os.path.join(OUT_DIR, "footprint.png"))
    print("  -> footprint.png (placeholder) saved")

    print("\nDone! All sprites generated in:", OUT_DIR)
    print("Review the output and adjust as needed.")

if __name__ == "__main__":
    main()
