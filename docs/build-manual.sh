#!/bin/sh
# Build A6 print-ready PDF from manual.md
# Requires: pandoc, weasyprint (pip install weasyprint), Google Chrome
# Font: Noto Sans CJK JP (apt install fonts-noto-cjk)

cd "$(dirname "$0")"

# 1. Render cover page to PDF (uses existing cover.jpg from img/)
echo ">>> Rendering cover page..."
weasyprint cover.html cover.pdf

# 3. Regenerate all other images using real app code
echo ""
echo ">>> Generating images..."
python3 generate_app_images.py

# 4. Build manual PDF (without cover)
echo ""
echo ">>> Building manual body..."
pandoc manual.md -o manual-body.pdf \
  --pdf-engine=weasyprint \
  --css=print.css \
  --metadata pagetitle="InkyPi 取扱説明書" \
  -V mainfont='Noto Sans CJK JP' \
  -V fontsize=7.5pt

# 5. Merge cover + manual body
echo ""
echo ">>> Merging cover + body..."
pdfunite cover.pdf manual-body.pdf manual.pdf

# 6. Clean up temp files
rm -f cover.pdf manual-body.pdf

echo "Done: $(pwd)/manual.pdf"
