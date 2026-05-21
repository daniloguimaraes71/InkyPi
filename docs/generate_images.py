#!/usr/bin/env python3
"""Generate manual images: plugin cards, web UI screenshots, interrupt cards.
Run from project root: python3 docs/generate_images.py"""

import sys, os, math, random

# --- bootstrap ---
SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))
os.environ["SRC_DIR"] = os.path.abspath(SRC)

from PIL import Image, ImageDraw, ImageFont
from utils.design_variants import VARIANTS
from utils.app_utils import get_font

OUT = os.path.join(os.path.dirname(__file__), "img")
os.makedirs(OUT, exist_ok=True)

W, H = 800, 480  # e-paper resolution

# --- helpers ---

def _font(name, size):
    f = get_font(name, size)
    if f is None:
        f = ImageFont.load_default()
    return f


def _load_variant(name="wa"):
    return VARIANTS.get(name, list(VARIANTS.values())[0])


def _month_name(m):
    names = ["", "1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]
    return names[m]


# ====================================================================
# 1.  plugins.jpg  — Morning Briefing card (e-paper style)
# ====================================================================

def gen_morning_briefing(path):
    v = _load_variant("wa")
    C = v.colors
    sm = v.spacing_mult

    img = Image.new("RGB", (W, H), C["bg"])
    d = ImageDraw.Draw(img)

    f_head = _font(v.heading_font, int(W * 0.045))
    f_body = _font(v.body_font, int(W * 0.025))
    f_sm = _font(v.body_font, int(W * 0.018))
    f_temp = _font(v.body_font, int(W * 0.055))

    # top accent line
    d.rectangle([(0, 0), (W, int(H * 0.015))], fill=C["accent"])

    # greeting
    d.text((int(W * 0.06), int(H * 0.07)), "おはようございます", font=f_head, fill=C["text_primary"])

    # date
    d.text((int(W * 0.06), int(H * 0.20)), "2026年5月21日（木）", font=f_body, fill=C["text_secondary"])

    # divider
    dy = int(H * 0.27)
    d.line([(int(W * 0.06), dy), (int(W * 0.94), dy)], fill=C["divider"], width=v.divider_width)

    # weather section
    wx_x = int(W * 0.06)
    wx_y = int(H * 0.31)
    d.text((wx_x, wx_y), "Today", font=_font(v.heading_font, int(W * 0.03)), fill=C["accent"])

    # temp
    d.text((wx_x, int(H * 0.39)), "22\u00b0", font=f_temp, fill=C["text_primary"])
    d.text((wx_x + int(W * 0.13), int(H * 0.42)), "晴れ", font=f_body, fill=C["text_secondary"])

    # details
    details = ["湿度 65%", "\u98a8 3m/s"]
    for i, t in enumerate(details):
        d.text((wx_x, int(H * 0.48) + i * int(H * 0.04)), t, font=f_sm, fill=C["text_light"])

    # calendar section (right side)
    cx = int(W * 0.48)
    d.text((cx, wx_y), "Today's Schedule", font=_font(v.heading_font, int(W * 0.03)), fill=C["accent"])

    events = [
        ("10:00", "\u4f1a\u8b70 with Team"),
        ("12:00", "\u30e9\u30f3\u30c1 \u6599\u7406\u4e88\u7d04"),
        ("15:00", "\u30d7\u30ed\u30b8\u30a7\u30af\u30c8\u9032\u635c"),
    ]
    ev_y = int(H * 0.39)
    for t, title in events:
        mt = _font(v.body_font, int(W * 0.022))
        d.text((cx, ev_y), t, font=mt, fill=C["text_primary"])
        d.text((cx + int(W * 0.14), ev_y), title, font=mt, fill=C["text_secondary"])
        ev_y += int(H * 0.055)

    # seasonal tag
    tag_y = int(H * 0.88)
    d.text((int(W * 0.06), tag_y), "五月晴れ  |  新緑の季節", font=f_sm, fill=C["text_light"])

    # bottom accent line
    d.rectangle([(0, int(H * 0.97)), (W, H)], fill=C["accent_sage"])

    img.save(path, quality=90)
    print(f"  Generated {path}")


# ====================================================================
# 2.  interrupt.jpg  — Calendar notification card
# ====================================================================

def gen_calendar_interrupt(path):
    v = _load_variant("ima")
    C = v.colors
    sm = v.spacing_mult

    img = Image.new("RGB", (W, H), C["bg"])
    d = ImageDraw.Draw(img)

    f_label = _font(v.body_font, int(W * 0.028))
    f_title = _font(v.heading_font, int(W * 0.05))
    f_time = _font(v.body_font, int(W * 0.03))

    cx = W // 2

    # label
    label = "\u6b21\u306e\u4e88\u5b9a"
    bb = d.textbbox((0, 0), label, font=f_label)
    d.text((cx - (bb[2] - bb[0]) // 2, int(H * 0.28)), label, font=f_label, fill=C["accent"])

    # event title
    title = "\u4f1a\u8b70 \u2014 \u56db\u5e63\u30d7\u30ed\u30b8\u30a7\u30af\u30c8"
    bb = d.textbbox((0, 0), title, font=f_title)
    tw = bb[2] - bb[0]
    if tw > W * 0.8:
        f_title = _font(v.heading_font, int(W * 0.038))
        bb = d.textbbox((0, 0), title, font=f_title)
        tw = bb[2] - bb[0]
    d.text((cx - tw // 2, int(H * 0.37)), title, font=f_title, fill=C["text_primary"])

    # divider
    dy = int(H * 0.48)
    dw = int(W * 0.12)
    d.line([(cx - dw, dy), (cx + dw, dy)], fill=C["divider"], width=v.divider_width * 2)

    # time
    time_str = "15\u5206\u5f8c"
    bb = d.textbbox((0, 0), time_str, font=f_time)
    d.text((cx - (bb[2] - bb[0]) // 2, int(H * 0.53)), time_str, font=f_time, fill=C["text_secondary"])

    # date
    f_date = _font(v.body_font, int(W * 0.018))
    date_str = "5\u670821\u65e5"
    bb = d.textbbox((0, 0), date_str, font=f_date)
    d.text((W - int(W * 0.05) - (bb[2] - bb[0]), int(H * 0.92)), date_str, font=f_date, fill=C["text_light"])

    img.save(path, quality=90)
    print(f"  Generated {path}")


# ====================================================================
# 3.  dashboard.jpg  — Web app dashboard (phone screenshot)
# ====================================================================

def gen_dashboard(path):
    # Phone-like portrait frame
    PW, PH = 390, 844
    img = Image.new("RGB", (PW, PH), (245, 245, 245))
    d = ImageDraw.Draw(img)

    # Phone bezel
    d.rectangle([(0, 0), (PW-1, PH-1)], outline=(200, 200, 200), width=2)
    d.rectangle([(8, 8), (PW-9, PH-9)], fill=(255, 255, 255))

    # Status bar
    d.rectangle([(8, 8), (PW-9, 40)], fill=(26, 188, 156))
    d.text((20, 14), "9:41", font=_font("Jost", 16), fill=(255,255,255))

    # Title bar
    d.text((20, 52), "InkyPi", font=_font("Jost", 22), fill=(50,50,50))

    # Navigation pills
    nav_items = ["Photos", "Mode", "Settings"]
    nx = PW - 20
    for item in reversed(nav_items):
        bb = d.textbbox((0, 0), item, font=_font("Noto Sans JP", 11))
        iw = bb[2] - bb[0]
        nx -= iw + 12
        d.text((nx, 56), item, font=_font("Noto Sans JP", 11), fill=(120,120,120))

    # Clock area
    clock_y = 90
    try:
        cf = _font("DS-Digital", 48)
    except:
        cf = _font("Jost", 48)
    d.text((PW//2 - 40, clock_y), "10:24", font=cf, fill=(50,50,50))

    # Status label
    d.text((PW//2 - 30, clock_y + 55), "Now Showing", font=_font("Noto Sans JP", 10), fill=(180,180,180))
    d.text((PW//2 - 35, clock_y + 70), "Morning Briefing", font=_font("Noto Sans JP", 12), fill=(26, 188, 156))

    # Mode badge
    d.rectangle([(PW//2 - 40, clock_y + 90), (PW//2 + 40, clock_y + 108)], fill=(26, 188, 156))
    d.text((PW//2 - 28, clock_y + 93), "Scheduled", font=_font("Noto Sans JP", 9), fill=(255,255,255))

    # Image preview
    iy = clock_y + 120
    d.rectangle([(40, iy), (PW-40, iy+150)], fill=(230, 230, 230), outline=(210,210,210))
    d.text((PW//2 - 30, iy + 65), "[preview]", font=_font("Noto Sans JP", 10), fill=(180,180,180))

    # Schedule section
    sy = iy + 170
    d.text((20, sy), "Today's Schedule", font=_font("Noto Sans JP", 14), fill=(50,50,50))

    schedule_items = [
        ("Morning Briefing", "06:30 - 07:30", True),
        ("Photos + Info", "07:30 - 12:00", False),
        ("Weather Detail", "12:00 - 12:30", False),
        ("Evening Card", "18:00 - 18:30", False),
        ("Goodnight Card", "21:00 - 21:15", False),
    ]

    siy = sy + 30
    for name, time, active in schedule_items:
        bg = (230, 248, 242) if active else (255, 255, 255)
        d.rectangle([(16, siy), (PW-16, siy+38)], fill=bg, outline=(235,235,235) if not active else None)
        if active:
            d.rectangle([(16, siy), (PW-16, siy+38)], fill=(26, 188, 156))
            d.text((30, siy+5), name, font=_font("Noto Sans JP", 11), fill=(255,255,255))
            d.text((30, siy+20), time, font=_font("Noto Sans JP", 9), fill=(220,255,245))
            # NOW badge
            d.rectangle([(PW-70, siy+6), (PW-30, siy+32)], fill=(255,255,255))
            d.text((PW-62, siy+10), "NOW", font=_font("Noto Sans JP", 8), fill=(255,255,255))
        else:
            d.text((30, siy+5), name, font=_font("Noto Sans JP", 11), fill=(80,80,80))
            d.text((30, siy+20), time, font=_font("Noto Sans JP", 9), fill=(160,160,160))
        siy += 42

    # Bottom bar
    d.rectangle([(8, PH-44), (PW-9, PH-9)], fill=(245,245,245), outline=(220,220,220))

    img.save(path, quality=90)
    print(f"  Generated {path}")


# ====================================================================
# 4.  schedule.jpg  — Settings page showing schedule editor
# ====================================================================

def gen_settings_schedule(path):
    PW, PH = 390, 844
    img = Image.new("RGB", (PW, PH), (245, 245, 245))
    d = ImageDraw.Draw(img)

    # White page background
    d.rectangle([(0, 0), (PW-1, PH-1)], fill=(255, 255, 255))

    # Status bar
    d.rectangle([(0, 0), (PW, 36)], fill=(26, 188, 156))
    d.text((16, 10), "9:41", font=_font("Jost", 14), fill=(255,255,255))

    # Title
    d.text((16, 46), "Settings", font=_font("Jost", 20), fill=(50,50,50))

    # Nav
    for i, lbl in enumerate(["Dashboard", "Photos", "Mode"]):
        x = PW - 220 + i * 75
        d.text((x, 50), lbl, font=_font("Noto Sans JP", 10), fill=(120,120,120))

    # --- Design Style section ---
    d.text((16, 86), "Design Style", font=_font("Noto Sans JP", 14), fill=(50,50,50))
    d.text((16, 104), "Choose visual style for cards", font=_font("Noto Sans JP", 9), fill=(160,160,160))

    # Style swatches
    swatches = [
        ("Wa", (245, 235, 215), (200, 170, 110)),
        ("Zen", (248, 248, 248), (180, 180, 180)),
        ("Ryoku", (255, 248, 235), (200, 80, 60)),
        ("Ima", (235, 242, 248), (140, 170, 190)),
    ]
    sx = 16
    for label, bg, accent in swatches:
        d.rectangle([(sx, 120), (sx+80, 170)], fill=bg, outline=(220,220,220))
        d.line([(sx+6, 130), (sx+74, 130)], fill=accent, width=2)
        d.rectangle([(sx+6, 135), (sx+20, 148)], fill=accent)
        d.text((sx+28, 150), label, font=_font("Noto Sans JP", 8), fill=(100,100,100))
        sx += 90

    # --- Photos section ---
    d.text((16, 190), "Photos", font=_font("Noto Sans JP", 14), fill=(50,50,50))
    d.text((16, 208), "How often to switch photos", font=_font("Noto Sans JP", 9), fill=(160,160,160))
    d.text((16, 226), "Every  5    Minute", font=_font("Noto Sans JP", 11), fill=(100,100,100))

    # --- Calendar section ---
    d.text((16, 260), "Calendar", font=_font("Noto Sans JP", 14), fill=(50,50,50))
    d.rectangle([(16, 278), (PW-16, 300)], fill=(245,245,245), outline=(220,220,220))
    d.text((22, 282), "https://calendar.google.com/...", font=_font("Noto Sans JP", 9), fill=(160,160,160))

    # --- Daily Schedule section ---
    dsy = 320
    d.rectangle([(12, dsy), (PW-12, dsy+34)], fill=(237, 235, 235), outline=(220,220,220))
    d.text((22, dsy+8), "Daily Schedule", font=_font("Noto Sans JP", 13), fill=(50,50,50))
    d.text((PW-40, dsy+8), "\u25bc", font=_font("Noto Sans JP", 10), fill=(120,120,120))

    # Mode rows
    modes_data = [
        ("Morning", ["mon","tue","wed","thu","fri"], "06:30", "07:30", "Card"),
        ("Photos + Info", ["mon","tue","wed","thu","fri","sat","sun"], "07:30", "18:00", "Photos"),
        ("Evening Card", ["mon","tue","wed","thu","fri","sat","sun"], "18:00", "18:30", "Card"),
    ]

    ry = dsy + 46
    for name, days, st, et, mtype in modes_data:
        d.rectangle([(12, ry), (PW-12, ry+80)], fill=(250,250,250), outline=(225,225,225))

        # header
        d.text((22, ry+4), name, font=_font("Noto Sans JP", 12), fill=(50,50,50))
        d.text((PW-50, ry+4), "\u2715", font=_font("Noto Sans JP", 12), fill=(200,60,60))

        # days
        day_labels = ["mon","tue","wed","thu","fri","sat","sun"]
        dx = 22
        for dl in day_labels:
            on = dl in days
            fcol = (26, 188, 156) if on else (180, 180, 180)
            d.text((dx, ry+24), dl, font=_font("Noto Sans JP", 8), fill=fcol)
            dx += 28

        # times
        d.text((22, ry+42), f"Start {st}", font=_font("Noto Sans JP", 8), fill=(100,100,100))
        d.text((120, ry+42), f"End {et}", font=_font("Noto Sans JP", 8), fill=(100,100,100))
        d.text((218, ry+42), "Every 300 sec", font=_font("Noto Sans JP", 8), fill=(100,100,100))

        # type
        mcol = (26, 188, 156) if mtype == "Card" else (142, 68, 173)
        d.text((22, ry+60), f"Type: {mtype}", font=_font("Noto Sans JP", 8), fill=mcol)
        if mtype == "Card":
            d.text((100, ry+60), "Card: morning_briefing", font=_font("Noto Sans JP", 8), fill=(120,120,120))
        else:
            d.text((100, ry+60), "Also show: calendar...", font=_font("Noto Sans JP", 8), fill=(120,120,120))

        ry += 88

    # Add time slot button
    d.rectangle([(12, ry+4), (PW-12, ry+30)], fill=(245,245,245), outline=(220,220,220))
    d.text((PW//2-30, ry+10), "+ Add Time Slot", font=_font("Noto Sans JP", 10), fill=(100,100,100))

    # Save button
    d.rectangle([(16, PH-50), (PW-16, PH-20)], fill=(26, 188, 156))
    d.text((PW//2-16, PH-42), "Save", font=_font("Noto Sans JP", 13), fill=(255,255,255))

    img.save(path, quality=90)
    print(f"  Generated {path}")


# ====================================================================
# 5.  Interrupt notification for weather (bonus / interrupt.jpg alt)
# ====================================================================

def gen_weather_alert(path):
    v = _load_variant("ryoku")
    C = v.colors

    img = Image.new("RGB", (W, H), C["bg_alt"])
    d = ImageDraw.Draw(img)

    f_label = _font(v.body_font, int(W * 0.028))
    f_title = _font(v.heading_font, int(W * 0.05))
    f_desc = _font(v.body_font, int(W * 0.024))

    cx = W // 2

    label = "\u6c17\u8c61\u8b66\u5831"
    bb = d.textbbox((0, 0), label, font=f_label)
    d.text((cx - (bb[2] - bb[0]) // 2, int(H * 0.26)), label, font=f_label, fill=C["accent_alt"])

    event = "\u5927\u96e8\u30fb\u66b4\u98a8\u8b66\u5831"
    bb = d.textbbox((0, 0), event, font=f_title)
    tw = bb[2] - bb[0]
    if tw > W * 0.8:
        f_title = _font(v.heading_font, int(W * 0.038))
        bb = d.textbbox((0, 0), event, font=f_title)
        tw = bb[2] - bb[0]
    d.text((cx - tw // 2, int(H * 0.35)), event, font=f_title, fill=C["text_primary"])

    dy = int(H * 0.46)
    dw = int(W * 0.12)
    d.line([(cx - dw, dy), (cx + dw, dy)], fill=C["divider"], width=v.divider_width * 2)

    desc = "\u5951\u7d04\u8005\u306f\u5c71\u304c\u3051\u30fb\u6cbc\u6f3e\u305a\u3001\u5ddd\u8fd1\u304f\u306b\u63a5\u8fd1\u3057\u306a\u3044\u3088\u3046\u306b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u5bb6\u5c4b\u306e\u6c34\u5bb3\u306b\u6ce8\u610f\u3002"
    f_desc_sm = _font(v.body_font, int(W * 0.022))

    line_y = int(H * 0.50)
    # word-wrap manually
    words = desc.split()
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bb = d.textbbox((0, 0), test, font=f_desc_sm)
        if bb[2] - bb[0] > W * 0.8 and current:
            d.text((cx - (d.textbbox((0,0), current, font=f_desc_sm)[2]-d.textbbox((0,0), current, font=f_desc_sm)[0])//2, line_y), current, font=f_desc_sm, fill=C["text_secondary"])
            line_y += int(H * 0.045)
            current = w
        else:
            current = test
    if current:
        d.text((cx - (d.textbbox((0,0), current, font=f_desc_sm)[2]-d.textbbox((0,0), current, font=f_desc_sm)[0])//2, line_y), current, font=f_desc_sm, fill=C["text_secondary"])

    f_date = _font(v.body_font, int(W * 0.018))
    date_str = "5\u670821\u65e5"
    bb = d.textbbox((0, 0), date_str, font=f_date)
    d.text((W - int(W * 0.05) - (bb[2] - bb[0]), int(H * 0.92)), date_str, font=f_date, fill=C["text_light"])

    img.save(path, quality=90)
    print(f"  Generated {path}")


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    print("Generating manual images...\n")

    gen_morning_briefing(os.path.join(OUT, "plugins.jpg"))
    gen_calendar_interrupt(os.path.join(OUT, "interrupt.jpg"))
    gen_dashboard(os.path.join(OUT, "dashboard.jpg"))
    gen_settings_schedule(os.path.join(OUT, "schedule.jpg"))
    gen_weather_alert(os.path.join(OUT, "weather_alert.jpg"))

    # Physical device images — we can't generate these, create a note
    for name in ["hero", "contents", "parts", "setup"]:
        path = os.path.join(OUT, f"{name}.jpg")
        img = Image.new("RGB", (800, 600), (220, 220, 220))
        d = ImageDraw.Draw(img)
        d.text((300, 280), f"[ {name} -- take photo ]", font=_font("Noto Sans JP", 18), fill=(120,120,120))
        img.save(path, quality=85)
        print(f"  Generated placeholder {path}")

    print("\nDone. Replace hero.jpg, contents.jpg, parts.jpg, setup.jpg with actual photos.")
