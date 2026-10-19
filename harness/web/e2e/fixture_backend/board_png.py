"""Tiny stand-in for a KiCad board render.

Each image carries a random code + a random coloured shape that the model can
only know by actually looking at the pixels. The ground truth is appended to a
server-side JSONL file (never sent to the model as text).
"""

import io
import json
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLORS = {
    'red': (215, 30, 30),
    'blue': (30, 70, 225),
    'green': (25, 165, 60),
    'orange': (245, 140, 0),
    'purple': (135, 45, 175),
}
SHAPES = ['circle', 'square', 'triangle']
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ'


def make_board_png(label: str, truth_path: Path) -> tuple[bytes, dict]:
    code = ''.join(random.choices(_ALPHABET, k=3)) + str(random.randint(2, 9))
    color = random.choice(list(COLORS))
    shape = random.choice(SHAPES)

    img = Image.new('RGB', (480, 300), (238, 236, 226))
    draw = ImageDraw.Draw(img)
    draw.text((20, 18), label, fill=(0, 0, 0), font=ImageFont.load_default(size=34))
    draw.text((20, 240), f'CODE: {code}', fill=(0, 0, 0), font=ImageFont.load_default(size=30))
    box = (300, 85, 440, 225)
    if shape == 'circle':
        draw.ellipse(box, fill=COLORS[color])
    elif shape == 'square':
        draw.rectangle(box, fill=COLORS[color])
    else:
        draw.polygon([(370, 85), (300, 225), (440, 225)], fill=COLORS[color])

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    truth = {'ts': time.time(), 'label': label, 'code': code, 'color': color, 'shape': shape}
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    with truth_path.open('a') as f:
        f.write(json.dumps(truth) + '\n')
    return buf.getvalue(), truth
