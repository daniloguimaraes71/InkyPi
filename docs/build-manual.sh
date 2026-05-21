#!/bin/sh
# Build A6 print-ready PDF from manual.md
# Requires: pandoc, weasyprint (pip install weasyprint), Google Chrome
# Font: Noto Sans CJK JP (apt install fonts-noto-cjk)

cd "$(dirname "$0")"

# 1. Regenerate all images using real app code
echo ">>> Generating images..."
python3 generate_app_images.py

# 2. Build PDF
echo ""
echo ">>> Building PDF..."
pandoc manual.md -o manual.pdf \
  --pdf-engine=weasyprint \
  --css=print.css \
  --metadata title="InkyPi 取扱説明書" \
  -V mainfont='Noto Sans CJK JP' \
  -V fontsize=7.5pt

echo "Done: $(pwd)/manual.pdf"
