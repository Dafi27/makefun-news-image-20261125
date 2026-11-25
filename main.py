#!/usr/bin/env python3
"""news-image-20261125: sum up Wednesday 25 November 2026 in one image.

Draws a 1024x1024 newspaper-style front page with the day's six most
consequential stories (COP31 collapse, Shenzhou-24 launch, Gaza strike,
NATO space defence, Huawei verdict, Ukraine war toll) and writes it to
/output/entry.png. Pure Python standard library, no network, deterministic.
"""
import os
import struct
import zlib
from binascii import crc32

W, H = 1024, 1024

# --- palette ---------------------------------------------------------------
PAPER = (251, 247, 238)
INK = (20, 33, 61)
NAVY = (20, 33, 61)
GOLD = (244, 211, 94)
RED = (198, 40, 40)
CARD = (255, 255, 255)
BORDER = (214, 206, 188)
SUB = (74, 74, 74)

# --- 5x7 bitmap font (each glyph: 7 rows of 5 bits) -------------------------
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
}

# --- canvas ----------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def rect(self, x, y, w, h, color):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, color)

    def hline(self, x, y, w, color):
        self.rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.rect(x, y, 1, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color, fill=False):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d2 <= r * r:
                        self.set(xx, yy, color)
                elif abs(d2 - r * r) <= r:
                    self.set(xx, yy, color)

    def text(self, x, y, s, scale, color):
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT[" "])
            for row in range(7):
                for col in range(5):
                    if glyph[row][col] == "1":
                        self.rect(cx + col * scale, y + row * scale,
                                  scale, scale, color)
            cx += 6 * scale

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_center(self, y, s, scale, color):
        self.text((self.w - self.text_width(s, scale)) // 2, y, s, scale, color)


# --- PNG encoder (filter 0, zlib, deterministic) ----------------------------
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(canvas, path):
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# --- pictograms (drawn inside a 92x92 icon box) -----------------------------
def icon_globe(c, x, y, color):
    cx, cy = x + 46, y + 46
    c.circle(cx, cy, 34, color)
    c.hline(cx - 34, cy, 69, color)
    c.hline(cx - 29, cy - 20, 59, color)
    c.hline(cx - 29, cy + 20, 59, color)
    for dx in (-17, 17):
        for yy in range(cy - 30, cy + 31):
            t = (yy - cy) / 30.0
            wdt = int(10 * (1 - t * t) ** 0.5)
            c.set(cx + dx - wdt, yy, color)
            c.set(cx + dx + wdt, yy, color)


def icon_rocket(c, x, y, color):
    cx = x + 46
    c.rect(cx - 9, y + 18, 18, 40, color)
    for i in range(10):
        c.rect(cx - 9 + i, y + 8 + i, 18 - 2 * i, 1, color)
    c.rect(cx - 20, y + 48, 11, 16, color)
    c.rect(cx + 9, y + 48, 11, 16, color)
    c.rect(cx - 4, y + 58, 8, 10, (244, 160, 60))
    c.rect(cx - 2, y + 68, 4, 8, (244, 160, 60))
    c.circle(cx, y + 32, 5, PAPER)


def icon_blast(c, x, y, color):
    cx, cy = x + 46, y + 46
    for k in range(12):
        ang = k * 30
        import math
        dx = int(38 * math.cos(math.radians(ang)))
        dy = int(38 * math.sin(math.radians(ang)))
        c.line(cx, cy, cx + dx, cy + dy, color)
    c.circle(cx, cy, 14, color, fill=True)
    c.circle(cx, cy, 6, PAPER, fill=True)


def icon_satellite(c, x, y, color):
    cx, cy = x + 46, y + 46
    c.rect(cx - 10, cy - 8, 20, 16, color)
    c.rect(cx - 40, cy - 12, 26, 24, color)
    c.rect(cx + 14, cy - 12, 26, 24, color)
    c.line(cx, cy - 8, cx + 12, cy - 30, color)
    c.circle(cx + 13, cy - 31, 3, color, fill=True)


def icon_chip(c, x, y, color):
    cx, cy = x + 46, y + 46
    c.rect(cx - 24, cy - 24, 48, 48, color)
    c.rect(cx - 12, cy - 12, 24, 24, PAPER)
    for i in range(4):
        px = cx - 18 + i * 12
        py = cy - 18 + i * 12
        c.rect(px, cy - 34, 6, 10, color)
        c.rect(px, cy + 24, 6, 10, color)
        c.rect(cx - 34, py, 10, 6, color)
        c.rect(cx + 24, py, 10, 6, color)


def icon_bars(c, x, y, color):
    cx, cy = x + 46, y + 46
    heights = (18, 32, 46)
    for i, hgt in enumerate(heights):
        bx = cx - 30 + i * 22
        c.rect(bx, cy + 24 - hgt, 16, hgt, color)
    c.hline(cx - 36, cy + 24, 76, color)
    c.vline(cx - 36, cy - 28, 54, color)


ICONS = (icon_globe, icon_rocket, icon_blast,
         icon_satellite, icon_chip, icon_bars)

# --- the day's news: Wednesday 25 November 2026 -----------------------------
# Headlines verified against BBC World (25 Nov 2026) and BD Global Times.
STORIES = [
    ("COP31 CLIMATE TALKS COLLAPSE",
     "Antalya summit ends with no deal as oil states block phaseout",
     (46, 125, 50)),
    ("SHENZHOU-24 LIFTS OFF WITH PAKISTANI ASTRONAUT",
     "China launches its first crew carrying a Pakistani astronaut",
     (21, 101, 192)),
    ("ISRAELI STRIKE KILLS HAMAS SECURITY CHIEF",
     "Gaza air strike kills Hamas internal security chief, officials say",
     (198, 40, 40)),
    ("NATO VOWS TO DEFEND SPACE",
     "Alliance acts after reports of a Russian nuclear-armed satellite",
     (40, 53, 147)),
    ("HUAWEI GUILTY OF STEALING TRADE SECRETS",
     "US jury convicts on trade secrets, acquits on racketeering",
     (0, 105, 92)),
    ("RUSSIA COUNTS NEARLY 500,000 WAR DEAD",
     "Moscow's own figures reveal the toll of the war in Ukraine",
     (69, 90, 100)),
]


def build():
    c = Canvas(W, H, PAPER)

    # header: masthead band with title and date
    c.rect(0, 0, W, 168, NAVY)
    c.text_center(28, "THE WORLD TODAY", 6, (255, 255, 255))
    c.text_center(104, "WEDNESDAY 25 NOVEMBER 2026", 3, GOLD)
    c.rect(0, 168, W, 6, RED)

    # six story cards
    y = 186
    for i, (head, sub, accent) in enumerate(STORIES):
        c.rect(20, y, 984, 124, CARD)
        c.rect(20, y, 984, 2, BORDER)
        c.rect(20, y + 122, 984, 2, BORDER)
        c.rect(20, y, 8, 124, accent)
        c.rect(1004, y, 2, 124, BORDER)
        ICONS[i](c, 40, y + 16, accent)
        c.text(150, y + 24, head, 3, INK)
        c.text(150, y + 74, sub.upper(), 2, SUB)
        y += 130

    # footer
    c.text_center(962,
                  "ALL STORIES REPORTED ON 25 NOVEMBER 2026 - SOURCES: BBC, REUTERS, AP",
                  2, SUB)
    return c


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(build(), path)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
