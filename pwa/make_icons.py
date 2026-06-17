"""앱 아이콘 생성 (PIL). 한 번 실행해 pwa/icons/*.png 생성.
실행: python pwa/make_icons.py   (conda 환경에 Pillow 포함)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "icons"
OUT.mkdir(exist_ok=True)


def make(size: int, bg, path: Path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 둥근 사각 배경
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18), fill=bg)
    # 흰색 의료 십자 (안전영역 안쪽 ~46%)
    arm = size * 0.14          # 십자 두께
    length = size * 0.46       # 십자 길이
    cx = cy = size / 2
    rad = int(arm / 3)
    d.rounded_rectangle([cx - arm / 2, cy - length / 2, cx + arm / 2, cy + length / 2], radius=rad, fill="white")
    d.rounded_rectangle([cx - length / 2, cy - arm / 2, cx + length / 2, cy + arm / 2], radius=rad, fill="white")
    img.save(path)
    print("wrote", path.name)


for name, bg in [("gen", (37, 99, 235, 255)), ("reader", (5, 150, 105, 255))]:
    for s in (192, 512):
        make(s, bg, OUT / f"{name}-{s}.png")
