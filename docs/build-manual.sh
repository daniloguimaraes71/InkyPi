#!/bin/sh
# Build A6 print-ready PDF from manual.md
# Requires: pandoc, weasyprint (pip install pandoc weasyprint)
# Font: Noto Sans CJK JP (apt install fonts-noto-cjk)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

pandoc "$SCRIPT_DIR/manual.md" -o "$SCRIPT_DIR/manual.pdf" \
  --pdf-engine=weasyprint \
  --css="$SCRIPT_DIR/print.css" \
  --metadata title="InkyPi 取扱説明書" \
  -V mainfont='Noto Sans CJK JP' \
  -V fontsize=7.5pt

echo "Generated $SCRIPT_DIR/manual.pdf"
