#!/bin/sh
# Build A6 print-ready PDF from manual.md
# Requires: pandoc, weasyprint (pip install weasyprint)
# Font: Noto Sans CJK JP (apt install fonts-noto-cjk)

cd "$(dirname "$0")"

pandoc manual.md -o manual.pdf \
  --pdf-engine=weasyprint \
  --css=print.css \
  --metadata title="InkyPi 取扱説明書" \
  -V mainfont='Noto Sans CJK JP' \
  -V fontsize=7.5pt

echo "Generated $(pwd)/manual.pdf"
