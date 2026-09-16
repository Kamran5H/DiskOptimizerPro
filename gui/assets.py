import os
from PIL import Image, ImageDraw

def generate_app_icon(output_dir: str):
    """
    Generates a sleek high-res .ico and .png icon for Disk Optimizer Pro.
    """
    os.makedirs(output_dir, exist_ok=True)
    ico_path = os.path.join(output_dir, "app_icon.ico")
    png_path = os.path.join(output_dir, "app_icon.png")

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for size in sizes:
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Outer rounded squircle background
        margin = max(1, int(w * 0.05))
        # Gradient simulated with concentric rounded rectangles
        steps = 15
        for i in range(steps):
            t = i / float(steps)
            # Interpolate deep slate blue (15, 23, 42) to bright cyan (6, 182, 212)
            r = int(15 + (14 - 15) * t)
            g = int(23 + (165 - 23) * t)
            b = int(42 + (233 - 42) * t)
            cur_margin = margin + int((steps - 1 - i) * (w * 0.02))
            draw.rounded_rectangle(
                [cur_margin, cur_margin, w - cur_margin, h - cur_margin],
                radius=int(w * 0.22),
                fill=(r, g, b, 255)
            )

        # Central drive plate
        dw = w * 0.65
        dh = h * 0.45
        dx0 = (w - dw) / 2
        dy0 = (h - dh) / 2 + (h * 0.05)
        draw.rounded_rectangle(
            [dx0, dy0, dx0 + dw, dy0 + dh],
            radius=int(w * 0.08),
            fill=(30, 41, 59, 240),
            outline=(56, 189, 248, 255),
            width=max(1, int(w * 0.025))
        )

        # Drive details: read/write LED and disk slot
        led_r = max(2, int(w * 0.035))
        led_x = dx0 + dw * 0.8
        led_y = dy0 + dh * 0.3
        draw.ellipse([led_x - led_r, led_y - led_r, led_x + led_r, led_y + led_r], fill=(34, 197, 94, 255))

        slot_x0 = dx0 + dw * 0.15
        slot_y0 = dy0 + dh * 0.65
        slot_x1 = dx0 + dw * 0.85
        slot_y1 = dy0 + dh * 0.75
        draw.rounded_rectangle([slot_x0, slot_y0, slot_x1, slot_y1], radius=max(1, int(w * 0.02)), fill=(51, 65, 85, 255))

        # Dynamic lightning bolt / spark representing speed and optimization
        bolt = [
            (w * 0.54, h * 0.15),
            (w * 0.38, h * 0.48),
            (w * 0.50, h * 0.48),
            (w * 0.44, h * 0.78),
            (w * 0.66, h * 0.42),
            (w * 0.52, h * 0.42),
        ]
        draw.polygon(bolt, fill=(250, 204, 21, 255), outline=(234, 179, 8, 255))

        images.append(img)

    # Save highest res as PNG
    images[0].save(png_path, "PNG")
    # Save multi-resolution ICO
    images[0].save(ico_path, format="ICO", sizes=[(im.width, im.height) for im in images])
    return ico_path, png_path

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
    ico, png = generate_app_icon(out_dir)
    print(f"Icons generated: {ico}, {png}")
