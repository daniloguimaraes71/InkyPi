#!/usr/bin/env python3
"""Generate a clean background photo for the cover page (no text overlay)."""

from __future__ import annotations
import sys, os, requests
from PIL import Image

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT, "docs", "img")
os.makedirs(OUT, exist_ok=True)

W, H = 1240, 1748  # A6 at 300 DPI

def generate_cover_bg():
    """Fetch a photo and produce a clean, slightly darkened background image."""
    photo = None
    try:
        url = "https://images.unsplash.com/photo-1499951360447-b19be8fe80f5?w=1240&h=1748&fit=crop&crop=center"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            photo = Image.open(__import__("io").BytesIO(resp.content))
    except Exception:
        pass

    if not photo:
        photo = Image.new("RGB", (W, H), (45, 50, 55))

    photo = photo.resize((W, H), Image.Resampling.LANCZOS)

    # Slight darken for text readability
    from PIL import ImageEnhance
    photo = ImageEnhance.Brightness(photo).enhance(0.65)

    path = os.path.join(OUT, "cover.jpg")
    photo.save(path, quality=95)
    print(f"  Saved cover.jpg ({W}x{H})")

if __name__ == "__main__":
    generate_cover_bg()
