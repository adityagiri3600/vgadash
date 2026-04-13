#!/usr/bin/env python3

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)


def load_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


FONT = load_font(28)
FONT_SMALL = load_font(21)
FONT_TINY = load_font(18)


def wrapped_lines(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_box(draw, xy, text, fill, font=FONT_SMALL):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline="black", width=3)
    max_width = x2 - x1 - 30
    lines = wrapped_lines(draw, text, font, max_width)
    line_height = 30 if font == FONT_SMALL else 24
    total_height = len(lines) * line_height
    start_y = y1 + ((y2 - y1) - total_height) // 2
    for idx, item in enumerate(lines):
        bbox = draw.textbbox((0, 0), item, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((x1 + ((x2 - x1) - text_width) // 2, start_y + idx * line_height), item, fill="black", font=font)


def draw_centered_text(draw, center_x, y, text, font=FONT_TINY):
    lines = wrapped_lines(draw, text, font, 250)
    line_height = 24
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        draw.text((center_x - width // 2, y + idx * line_height), line, fill="black", font=font)


def arrow(draw, start, end):
    draw.line([start, end], fill="black", width=4)
    ex, ey = end
    sx, sy = start
    dx = ex - sx
    dy = ey - sy
    if abs(dx) > abs(dy):
        sign = 1 if dx > 0 else -1
        draw.polygon([(ex, ey), (ex - 18 * sign, ey - 10), (ex - 18 * sign, ey + 10)], fill="black")
    else:
        sign = 1 if dy > 0 else -1
        draw.polygon([(ex, ey), (ex - 10, ey - 18 * sign), (ex + 10, ey - 18 * sign)], fill="black")


def make_architecture():
    img = Image.new("RGB", (1600, 820), "white")
    draw = ImageDraw.Draw(img)

    draw_box(draw, (70, 70, 470, 190), "Kernel Events and printk Messages", "#d9e8fb")
    draw_box(draw, (70, 260, 470, 380), "Userspace Logging and Retrieval", "#f7d8d8")
    draw_box(draw, (70, 450, 470, 570), "Storage / Network / GUI Access", "#f7d8d8")
    draw_box(draw, (70, 640, 470, 760), "Operator", "#f7d8d8")

    draw_box(draw, (690, 70, 1070, 190), "Kernel Events and printk Messages", "#d9e8fb")
    draw_box(draw, (690, 290, 1070, 430), "VGADASH In-Kernel Dashboard Path", "#fde7c7")
    draw_box(draw, (1190, 70, 1520, 190), "Keyboard / SysRq", "#dff4df")
    draw_box(draw, (1190, 290, 1520, 430), "VGA Text Overlay", "#dff4df")
    draw_box(draw, (1190, 580, 1520, 700), "Operator", "#dff4df")

    arrow(draw, (270, 190), (270, 260))
    arrow(draw, (270, 380), (270, 450))
    arrow(draw, (270, 570), (270, 640))

    arrow(draw, (880, 190), (880, 290))
    arrow(draw, (1190, 130), (1070, 360))
    arrow(draw, (1070, 360), (1190, 360))
    arrow(draw, (1355, 430), (1355, 580))

    draw_centered_text(draw, 270, 208, "Fails if journald or shell is unavailable")
    draw_centered_text(draw, 270, 398, "Fails if storage, graphics, or network path breaks")
    draw_centered_text(draw, 880, 220, "Shortens the dependency chain")
    draw_centered_text(draw, 1355, 208, "Emergency control path")

    img.save(ASSETS / "architecture.png")


def make_workflow():
    img = Image.new("RGB", (1600, 760), "white")
    draw = ImageDraw.Draw(img)

    boxes = [
        ((70, 70, 300, 190), "Keyboard Keypress"),
        ((370, 70, 640, 190), "SysRq Handler"),
        ((720, 70, 1010, 190), "Deferred Work"),
        ((1090, 70, 1420, 190), "Page Selection"),
        ((100, 390, 430, 550), "Logs Page or State Page"),
        ((560, 390, 930, 550), "VGA Overlay Save and Render"),
        ((1080, 390, 1460, 550), "Operator Sees Dashboard"),
    ]
    fills = ["#d9e8fb", "#fde7c7", "#fde7c7", "#dff4df", "#e9defa", "#dff4df", "#d9e8fb"]
    for (xy, text), fill in zip(boxes, fills):
        draw_box(draw, xy, text, fill)

    arrow(draw, (300, 130), (370, 130))
    arrow(draw, (640, 130), (720, 130))
    arrow(draw, (1010, 130), (1090, 130))
    arrow(draw, (1255, 190), (1255, 300))
    arrow(draw, (1255, 300), (265, 390))
    arrow(draw, (430, 470), (560, 470))
    arrow(draw, (930, 470), (1080, 470))

    draw_centered_text(draw, 185, 220, "Alt+SysRq+v, g, y")
    draw_centered_text(draw, 505, 220, "Minimal emergency entrypoint")
    draw_centered_text(draw, 865, 220, "Avoid heavy work in handler")
    draw_centered_text(draw, 1255, 220, "Choose logs or state view")

    img.save(ASSETS / "workflow.png")


if __name__ == "__main__":
    make_architecture()
    make_workflow()
