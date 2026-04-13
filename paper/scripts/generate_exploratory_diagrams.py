#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)

PALETTE = {
    'bg': '#f6f7fb',
    'ink': '#1a1f36',
    'muted': '#5b6480',
    'blue': '#cfe0ff',
    'blue_dark': '#335bdb',
    'green': '#d9f0d8',
    'green_dark': '#2f7d32',
    'orange': '#fde4bc',
    'orange_dark': '#b96811',
    'rose': '#f8d4d3',
    'rose_dark': '#b43a3a',
    'gold': '#fff0bf',
    'lav': '#e7ddff',
    'line': '#d9deeb',
    'card': '#ffffff',
}


def font(size, bold=False):
    choices = []
    if bold:
        choices += [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
        ]
    choices += [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
    ]
    for p in choices:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

F_TITLE = font(42, True)
F_SUB = font(22)
F_CARD = font(24, True)
F_BODY = font(20)
F_SMALL = font(17)
F_BADGE = font(16, True)
F_STEP = font(18, True)


def gradient(size, top, bottom):
    img = Image.new('RGB', size, top)
    draw = ImageDraw.Draw(img)
    w, h = size
    tr = int(top[1:3], 16), int(top[3:5], 16), int(top[5:7], 16)
    br = int(bottom[1:3], 16), int(bottom[3:5], 16), int(bottom[5:7], 16)
    for y in range(h):
        t = y / max(h - 1, 1)
        rgb = tuple(int(tr[i] + (br[i] - tr[i]) * t) for i in range(3))
        draw.line((0, y, w, y), fill=rgb)
    return img


def add_shadow(base, xy, radius=26, alpha=60):
    x1, y1, x2, y2 = xy
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((x1+8, y1+10, x2+8, y2+10), radius=radius, fill=(20, 28, 45, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(shadow)


def rounded_card(draw, xy, fill='white', outline=None, width=2, radius=26):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline or fill, width=width)


def wrap(draw, text, fnt, max_w):
    words = text.split()
    lines, line = [], ''
    for word in words:
        cand = (line + ' ' + word).strip()
        if draw.textbbox((0,0), cand, font=fnt)[2] <= max_w or not line:
            line = cand
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def text_block(draw, xy, text, fnt, fill, align='left', line_gap=7):
    x1, y1, x2, y2 = xy
    lines = wrap(draw, text, fnt, x2 - x1)
    bbox = draw.textbbox((0,0), 'Ag', font=fnt)
    lh = (bbox[3]-bbox[1]) + line_gap
    y = y1
    for line in lines:
        tw = draw.textbbox((0,0), line, font=fnt)[2]
        x = x1 if align == 'left' else x1 + (x2 - x1 - tw)//2
        draw.text((x, y), line, font=fnt, fill=fill)
        y += lh
    return y


def badge(draw, xy, text, fill, ink='white'):
    rounded_card(draw, xy, fill=fill, outline=fill, width=1, radius=15)
    x1, y1, x2, y2 = xy
    tw = draw.textbbox((0,0), text, font=F_BADGE)[2]
    th = draw.textbbox((0,0), text, font=F_BADGE)[3]
    draw.text((x1 + (x2-x1-tw)//2, y1 + (y2-y1-th)//2 - 2), text, font=F_BADGE, fill=ink)


def arrow(draw, start, end, fill, width=5, head=16):
    draw.line([start, end], fill=fill, width=width)
    ex, ey = end
    sx, sy = start
    dx, dy = ex - sx, ey - sy
    if abs(dx) >= abs(dy):
        s = 1 if dx > 0 else -1
        pts = [(ex, ey), (ex - head*s, ey - head//2), (ex - head*s, ey + head//2)]
    else:
        s = 1 if dy > 0 else -1
        pts = [(ex, ey), (ex - head//2, ey - head*s), (ex + head//2, ey - head*s)]
    draw.polygon(pts, fill=fill)


def dashed(draw, start, end, fill, width=4, dash=16, gap=10):
    x1, y1 = start; x2, y2 = end
    length = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
    if length == 0:
        return
    dx, dy = (x2-x1)/length, (y2-y1)/length
    dist = 0
    while dist < length:
        seg = min(dash, length - dist)
        sx, sy = x1 + dx*dist, y1 + dy*dist
        ex, ey = x1 + dx*(dist+seg), y1 + dy*(dist+seg)
        draw.line((sx, sy, ex, ey), fill=fill, width=width)
        dist += dash + gap


def icon_monitor(draw, x, y, c):
    draw.rounded_rectangle((x, y, x+80, y+52), radius=10, outline=c, width=4)
    draw.rectangle((x+28, y+56, x+52, y+64), fill=c)
    draw.rounded_rectangle((x+18, y+64, x+62, y+72), radius=4, fill=c)


def icon_keyboard(draw, x, y, c):
    draw.rounded_rectangle((x, y, x+84, y+48), radius=10, outline=c, width=4)
    for r in range(3):
        for col in range(7):
            xx = x+10+col*10
            yy = y+10+r*10
            draw.rounded_rectangle((xx, yy, xx+7, yy+6), radius=2, fill=c)


def icon_stack(draw, x, y, c):
    for off in [0, 10, 20]:
        draw.rounded_rectangle((x+off, y+off, x+80+off, y+40+off), radius=10, outline=c, width=4)


def icon_chip(draw, x, y, c):
    draw.rounded_rectangle((x+10, y+10, x+70, y+70), radius=10, outline=c, width=4)
    for px in [0, 84]:
        for py in [18, 34, 50]:
            draw.rectangle((x+px, y+py, x+10+px, y+py+4), fill=c)
    for py in [0, 84]:
        for px in [18, 34, 50]:
            draw.rectangle((x+px, y+py, x+px+4, y+10+py), fill=c)


def title(draw, x, y, text, sub=None):
    draw.text((x, y), text, font=F_TITLE, fill=PALETTE['ink'])
    if sub:
        text_block(draw, (x, y+56, x+1200, y+120), sub, F_SUB, PALETTE['muted'])


def candidate_observability_gap():
    base = gradient((2200, 1400), '#fcfdff', '#eef3fb').convert('RGBA')
    draw = ImageDraw.Draw(base)
    title(draw, 90, 70, 'Candidate A: Failure-Time Observability Gap', 'A richer split-view figure showing how conventional observability breaks across multiple dependencies while VGADASH preserves a short kernel-to-screen recovery path.')

    left = (80, 220, 1010, 1250)
    right = (1120, 220, 2120, 1250)
    add_shadow(base, left)
    add_shadow(base, right)
    rounded_card(draw, left, fill=PALETTE['card'], outline=PALETTE['line'])
    rounded_card(draw, right, fill=PALETTE['card'], outline=PALETTE['line'])

    badge(draw, (120, 255, 325, 300), 'Conventional path', PALETTE['rose_dark'])
    badge(draw, (1160, 255, 1340, 300), 'VGADASH path', PALETTE['green_dark'])

    draw.text((130, 335), 'When the normal stack works', font=F_CARD, fill=PALETTE['ink'])
    draw.text((1170, 335), 'When the system is alive but degraded', font=F_CARD, fill=PALETTE['ink'])

    # left chain
    left_boxes = [
        ((160, 430, 520, 550), 'Kernel events\nand printk', PALETTE['blue']),
        ((160, 630, 520, 750), 'Userspace log\nconsumers', PALETTE['rose']),
        ((160, 830, 520, 950), 'Storage, GUI,\nremote shell', PALETTE['rose']),
        ((160, 1030, 520, 1150), 'Operator', PALETTE['rose']),
    ]
    for (xy, txt, fill) in left_boxes:
        rounded_card(draw, xy, fill=fill, outline=PALETTE['ink'])
        text_block(draw, (xy[0]+28, xy[1]+28, xy[2]-28, xy[3]-20), txt, F_CARD, PALETTE['ink'], 'center', 4)
    icon_chip(draw, 610, 448, PALETTE['blue_dark'])
    icon_stack(draw, 610, 648, PALETTE['rose_dark'])
    icon_monitor(draw, 610, 850, PALETTE['rose_dark'])

    arrow(draw, (340, 550), (340, 630), PALETTE['ink'])
    arrow(draw, (340, 750), (340, 830), PALETTE['ink'])
    arrow(draw, (340, 950), (340, 1030), PALETTE['ink'])
    arrow(draw, (520, 490), (610, 490), PALETTE['line'], width=4)
    arrow(draw, (520, 690), (610, 690), PALETTE['line'], width=4)
    arrow(draw, (520, 890), (610, 890), PALETTE['line'], width=4)

    failure_card = (640, 380, 940, 980)
    rounded_card(draw, failure_card, fill='#fff8e6', outline='#e1c46a')
    draw.text((675, 415), 'Failure points', font=F_CARD, fill=PALETTE['orange_dark'])
    failures = [
        ('Userspace init', 'journalctl -k and shells never become usable'),
        ('Graphics handoff', 'compositor or framebuffer path fails'),
        ('Storage path', 'mount or disk access breaks persistence'),
        ('Network path', 'SSH and remote logging disappear'),
    ]
    y = 485
    for head, body in failures:
        badge(draw, (675, y, 840, y+34), head, PALETTE['gold'], ink=PALETTE['orange_dark'])
        text_block(draw, (675, y+48, 910, y+110), body, F_SMALL, PALETTE['ink'])
        y += 125

    dashed(draw, (640, 475), (520, 690), PALETTE['rose_dark'])
    dashed(draw, (640, 620), (520, 890), PALETTE['rose_dark'])
    dashed(draw, (640, 765), (520, 1090), PALETTE['rose_dark'])

    # right path
    right_boxes = [
        ((1190, 430, 1530, 550), 'Kernel events\nand printk', PALETTE['blue']),
        ((1190, 670, 1530, 830), 'VGADASH in-kernel\nlog/state surface', PALETTE['orange']),
        ((1670, 430, 2010, 550), 'Keyboard\nSysRq', PALETTE['green']),
        ((1670, 670, 2010, 830), 'VGA text\noverlay', PALETTE['green']),
        ((1670, 970, 2010, 1090), 'Operator', PALETTE['green']),
    ]
    for (xy, txt, fill) in right_boxes:
        rounded_card(draw, xy, fill=fill, outline=PALETTE['ink'])
        text_block(draw, (xy[0]+28, xy[1]+28, xy[2]-28, xy[3]-20), txt, F_CARD, PALETTE['ink'], 'center', 4)
    icon_chip(draw, 1560, 448, PALETTE['blue_dark'])
    icon_keyboard(draw, 1560, 448, PALETTE['green_dark'])
    icon_monitor(draw, 1560, 708, PALETTE['green_dark'])

    arrow(draw, (1360, 550), (1360, 670), PALETTE['ink'])
    arrow(draw, (1670, 490), (1530, 730), PALETTE['ink'])
    arrow(draw, (1530, 750), (1670, 750), PALETTE['ink'])
    arrow(draw, (1840, 830), (1840, 970), PALETTE['ink'])

    rounded_card(draw, (1190, 930, 1530, 1170), fill='#eff5ff', outline='#b7caef')
    draw.text((1220, 960), 'What remains available', font=F_CARD, fill=PALETTE['blue_dark'])
    points = [
        'Recent kernel log activity',
        'Compact local state summary',
        'Keyboard-driven entry path',
        'No reliance on SSH or GUI',
    ]
    yy = 1010
    for p in points:
        draw.ellipse((1222, yy+9, 1234, yy+21), fill=PALETTE['blue_dark'])
        draw.text((1250, yy), p, font=F_SMALL, fill=PALETTE['ink'])
        yy += 42

    out = ASSETS / 'candidate_observability_gap.png'
    base.convert('RGB').save(out, quality=95)
    print(out)


def candidate_runtime_swimlane():
    base = gradient((2200, 1450), '#fdfefe', '#eef2fb').convert('RGBA')
    draw = ImageDraw.Draw(base)
    title(draw, 90, 70, 'Candidate B: SysRq-Driven Runtime Interaction', 'A denser swimlane diagram showing how VGADASH stays usable by keeping control close to the keyboard and deferring non-trivial rendering work.')

    lanes = [
        ('Operator', PALETTE['blue']),
        ('Keyboard / SysRq', PALETTE['green']),
        ('SysRq handler', PALETTE['orange']),
        ('Deferred work', PALETTE['orange']),
        ('Page manager', PALETTE['lav']),
        ('VGA renderer', PALETTE['green']),
    ]
    x_positions = [120, 460, 800, 1140, 1480, 1820]
    top, bottom = 280, 1230
    for (name, fill), x in zip(lanes, x_positions):
        add_shadow(base, (x, 240, x+240, 1310), radius=24, alpha=40)
        rounded_card(draw, (x, 240, x+240, 1310), fill='white', outline=PALETTE['line'])
        rounded_card(draw, (x+20, 260, x+220, 330), fill=fill, outline=PALETTE['ink'], radius=18)
        text_block(draw, (x+40, 280, x+200, 320), name, F_CARD, PALETTE['ink'], 'center')
        dashed(draw, (x+120, 340), (x+120, 1260), PALETTE['line'], width=3, dash=12, gap=12)

    steps = [
        (1, 120, 410, 700, 'Press Alt+SysRq+v to toggle, or g and y to jump directly to logs and state.'),
        (2, 460, 530, 1040, 'Keyboard delivery reaches the emergency SysRq path instead of relying on a shell command.'),
        (3, 800, 650, 1380, 'The handler does the smallest possible amount of work and schedules a safer follow-up stage.'),
        (4, 1140, 790, 1700, 'Deferred work resolves whether the action is toggle, logs, or state.'),
        (5, 1480, 930, 2040, 'Page manager chooses the view and prepares the overlay update.'),
        (6, 1820, 1090, 2040, 'Renderer saves the prior screen, draws the dashboard, and returns a readable local display.'),
    ]
    for num, x1, y, x2, body in steps:
        bubble = (x1+20, y-18, x1+62, y+24)
        rounded_card(draw, bubble, fill=PALETTE['ink'], outline=PALETTE['ink'], radius=14)
        draw.text((x1+34, y-6), str(num), font=F_STEP, fill='white')
        rounded_card(draw, (x1+80, y-28, x2, y+42), fill='white', outline=PALETTE['line'], radius=18)
        text_block(draw, (x1+100, y-8, x2-20, y+80), body, F_SMALL, PALETTE['ink'])

    arrow(draw, (360, 430), (460, 430), PALETTE['blue_dark'])
    arrow(draw, (700, 550), (800, 550), PALETTE['green_dark'])
    arrow(draw, (1040, 670), (1140, 670), PALETTE['orange_dark'])
    arrow(draw, (1380, 810), (1480, 810), PALETTE['orange_dark'])
    arrow(draw, (1700, 950), (1820, 950), PALETTE['muted'])
    arrow(draw, (1940, 1130), (240, 1130), PALETTE['green_dark'])

    rounded_card(draw, (120, 1120, 360, 1240), fill=PALETTE['blue'], outline=PALETTE['ink'])
    text_block(draw, (150, 1145, 330, 1210), 'Dashboard becomes visible to the operator', F_CARD, PALETTE['ink'], 'center')

    right_panel = (1480, 360, 2050, 700)
    rounded_card(draw, right_panel, fill='#fff9ec', outline='#e7c984')
    draw.text((1520, 395), 'Key mapping summary', font=F_CARD, fill=PALETTE['orange_dark'])
    items = [
        ('Alt+SysRq+v', 'toggle overlay on or off'),
        ('Alt+SysRq+g', 'show logs page immediately'),
        ('Alt+SysRq+y', 'show state page immediately'),
    ]
    yy = 465
    for key, desc in items:
        badge(draw, (1520, yy, 1690, yy+36), key, PALETTE['ink'])
        text_block(draw, (1710, yy+3, 2010, yy+60), desc, F_SMALL, PALETTE['ink'])
        yy += 88

    out = ASSETS / 'candidate_runtime_swimlane.png'
    base.convert('RGB').save(out, quality=95)
    print(out)


def candidate_tool_matrix():
    base = gradient((2200, 1300), '#fcfdff', '#eef3fb').convert('RGBA')
    draw = ImageDraw.Draw(base)
    title(draw, 90, 70, 'Candidate C: Tool Positioning Matrix', 'A figure-style comparison that may work better than a dense text table if you want the evaluation section to feel more visual.')

    rounded_card(draw, (90, 210, 2110, 1180), fill='white', outline=PALETTE['line'])
    cols = ['Works without\nuserspace', 'Needs\nnetwork', 'On-screen\nvisibility', 'Live state\nsummary', 'Best fit']
    rows = [
        ('VGADASH', ['yes', 'no', 'yes', 'yes', 'Alive-but-unusable systems']),
        ('SysRq', ['yes', 'no', 'no', 'no', 'Emergency commands only']),
        ('netconsole', ['yes', 'yes', 'no', 'no', 'Remote log export']),
        ('pstore / ramoops', ['partial', 'no', 'no', 'no', 'Post-reboot evidence']),
        ('kdump', ['partial', 'no', 'no', 'partial', 'Post-mortem crash capture']),
        ('earlyprintk', ['yes', 'no', 'sometimes', 'no', 'Very early boot only']),
    ]
    x0, y0 = 150, 310
    row_h = 118
    col_w = [300, 220, 220, 220, 220, 520]
    xs = [x0]
    for w in col_w[:-1]:
        xs.append(xs[-1] + w)

    headers = ['Tool'] + cols
    for i, h in enumerate(headers):
        rounded_card(draw, (xs[i], y0, xs[i]+col_w[i]-18, y0+84), fill=PALETTE['blue'], outline=PALETTE['ink'], radius=18)
        text_block(draw, (xs[i]+12, y0+18, xs[i]+col_w[i]-30, y0+70), h.replace('\\n',' '), F_SMALL, PALETTE['ink'], 'center')

    colors = {'yes': ('#daf3da', PALETTE['green_dark'], 'Yes'), 'no': ('#f8d4d3', PALETTE['rose_dark'], 'No'), 'partial': ('#fff0bf', PALETTE['orange_dark'], 'Partial'), 'sometimes': ('#e7ddff', '#5f46b2', 'Sometimes')}
    for r, (tool, vals) in enumerate(rows, 1):
        y = y0 + r*row_h
        rounded_card(draw, (xs[0], y, xs[0]+col_w[0]-18, y+88), fill='#f9fbff', outline=PALETTE['line'], radius=18)
        text_block(draw, (xs[0]+20, y+24, xs[0]+col_w[0]-40, y+70), tool, F_CARD, PALETTE['ink'], 'center')
        for c, val in enumerate(vals[:4], 1):
            fill, ink, label = colors[val]
            rounded_card(draw, (xs[c]+28, y+18, xs[c]+col_w[c]-46, y+70), fill=fill, outline=ink, radius=20)
            text_block(draw, (xs[c]+44, y+32, xs[c]+col_w[c]-62, y+60), label, F_BADGE, ink, 'center')
        rounded_card(draw, (xs[5], y, xs[5]+col_w[5]-18, y+88), fill='#f9fbff', outline=PALETTE['line'], radius=18)
        text_block(draw, (xs[5]+24, y+22, xs[5]+col_w[5]-46, y+74), vals[4], F_SMALL, PALETTE['ink'])

    badge(draw, (145, 1135, 390, 1175), 'Possible figure alternative', PALETTE['blue_dark'])
    text_block(draw, (420, 1138, 1900, 1175), 'This matrix can stay as a figure candidate, while the paper keeps the Word-native table if that looks cleaner in the template.', F_SMALL, PALETTE['muted'])

    out = ASSETS / 'candidate_tool_matrix.png'
    base.convert('RGB').save(out, quality=95)
    print(out)


if __name__ == '__main__':
    candidate_observability_gap()
    candidate_runtime_swimlane()
    candidate_tool_matrix()
