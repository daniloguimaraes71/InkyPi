"""
Design system for Kansai Companion cards.
Provides elegant, consistent styling across all card types.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from utils.app_utils import get_font
from utils.micro_season import get_seasonal_palette
import logging

logger = logging.getLogger(__name__)


class CardDesign:
    """Unified design system for all Kansai Companion cards."""
    
    # Color constants - elegant muted palette
    COLORS = {
        'bg_warm': '#FAF8F5',
        'bg_cool': '#F5F7FA',
        'bg_dark': '#1A1A2E',
        'text_primary': '#2C2C2C',
        'text_secondary': '#666666',
        'text_light': '#999999',
        'accent_gold': '#8B7355',
        'accent_copper': '#B87333',
        'divider': '#E0D8C8',
    }
    
    def __init__(self, dimensions, orientation='horizontal'):
        self.w, self.h = dimensions
        if orientation == 'vertical':
            self.w, self.h = self.h, self.w
        
        # Grid system - 12 column grid
        self.margin = int(self.w * 0.06)
        self.gutter = int(self.w * 0.02)
        self.col_width = (self.w - 2 * self.margin - 11 * self.gutter) // 12
        
        # Font sizes - responsive to width
        self.font_sizes = {
            'display': int(self.w * 0.09),    # Large display text
            'h1': int(self.w * 0.065),        # Main heading
            'h2': int(self.w * 0.05),         # Section heading
            'h3': int(self.w * 0.04),         # Subsection
            'body': int(self.w * 0.035),      # Body text
            'caption': int(self.w * 0.03),    # Captions
            'micro': int(self.w * 0.025),     # Small labels
        }
        
        # Load fonts
        self.fonts = {
            'display': get_font('Noto Serif JP', self.font_sizes['display']),
            'h1': get_font('Noto Serif JP', self.font_sizes['h1']),
            'h2': get_font('Noto Serif JP', self.font_sizes['h2']),
            'h3': get_font('Noto Sans JP', self.font_sizes['h3']),
            'body': get_font('Noto Sans JP', self.font_sizes['body']),
            'caption': get_font('Noto Sans JP', self.font_sizes['caption']),
            'micro': get_font('Noto Sans JP', self.font_sizes['micro']),
        }
    
    def get_x(self, col, span=1):
        """Get x position for grid column."""
        return self.margin + col * (self.col_width + self.gutter)
    
    def get_width(self, span):
        """Get width for grid span."""
        return span * self.col_width + (span - 1) * self.gutter
    
    def create_base_card(self, bg_color=None, palette=None):
        """Create a base card with elegant background."""
        if bg_color is None:
            bg_color = self.COLORS['bg_warm']
        
        from PIL import ImageColor
        bg = ImageColor.getcolor(bg_color, 'RGB')
        img = Image.new('RGBA', (self.w, self.h), bg + (255,))
        
        # Add subtle texture/gradient if palette available
        if palette:
            self._add_subtle_gradient(img, palette)
        
        return img
    
    def _add_subtle_gradient(self, img, palette):
        """Add subtle gradient overlay for depth."""
        draw = ImageDraw.Draw(img)
        
        # Very subtle top gradient - opaque version
        base_color = img.getpixel((0, 0))[:3]  # Get background color
        for y in range(int(self.h * 0.15)):
            # Blend towards slightly lighter version
            factor = 1 - (y / (self.h * 0.15))
            r = min(255, int(base_color[0] + (255 - base_color[0]) * 0.05 * factor))
            g = min(255, int(base_color[1] + (255 - base_color[1]) * 0.05 * factor))
            b = min(255, int(base_color[2] + (255 - base_color[2]) * 0.05 * factor))
            draw.line([(0, y), (self.w, y)], fill=(r, g, b, 255))
    
    def draw_header(self, draw, title, subtitle=None, y_start=None):
        """Draw elegant header with title and optional subtitle."""
        if y_start is None:
            y_start = int(self.h * 0.08)
        
        # Title
        draw.text((self.margin, y_start), title, font=self.fonts['h1'], fill=self.COLORS['text_primary'])
        
        if subtitle:
            draw.text((self.margin, y_start + int(self.h * 0.06)), subtitle, 
                     font=self.fonts['caption'], fill=self.COLORS['text_secondary'])
        
        # Elegant divider line
        div_y = y_start + int(self.h * 0.10)
        draw.line([(self.margin, div_y), (self.w - self.margin, div_y)], 
                 fill=self.COLORS['divider'], width=1)
        
        return div_y + int(self.h * 0.04)
    
    def draw_section(self, draw, title, y_start, accent_color=None):
        """Draw section header with accent line."""
        if accent_color is None:
            accent_color = self.COLORS['accent_gold']
        
        # Accent line
        draw.line([(self.margin, y_start), (self.margin + int(self.w * 0.03), y_start)], 
                 fill=accent_color, width=2)
        
        # Section title
        draw.text((self.margin + int(self.w * 0.04), y_start - int(self.h * 0.01)), 
                 title, font=self.fonts['micro'], fill=accent_color)
        
        return y_start + int(self.h * 0.04)
    
    def draw_text_block(self, draw, text, x, y, font_key='body', color=None, max_width=None):
        """Draw text with proper wrapping."""
        if color is None:
            color = self.COLORS['text_primary']
        
        font = self.fonts[font_key]
        
        if max_width is None:
            max_width = self.w - x - self.margin
        
        # Simple text wrapping
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # Draw lines
        line_height = int(self.font_sizes[font_key] * 1.4)
        for i, line in enumerate(lines):
            draw.text((x, y + i * line_height), line, font=font, fill=color)
        
        return y + len(lines) * line_height
    
    def draw_footer(self, draw, date_str, season_info=None, show_season=True):
        """Draw elegant footer with date and micro-season."""
        footer_y = int(self.h * 0.88)
        
        # Divider
        draw.line([(self.margin, footer_y), (self.w - self.margin, footer_y)], 
                 fill=self.COLORS['divider'], width=1)
        
        # Date
        draw.text((self.margin, footer_y + int(self.h * 0.03)), 
                 date_str, font=self.fonts['micro'], fill=self.COLORS['text_secondary'])
        
        # Micro-season - only if requested
        if season_info and show_season:
            season_label = f"時候: {season_info['micro_season']['kanji']}"
            season_meaning = season_info['micro_season']['english']
            
            draw.text((self.w - self.margin, footer_y + int(self.h * 0.03)), 
                     season_label, font=self.fonts['micro'], fill=self.COLORS['accent_gold'], anchor='rt')
            draw.text((self.w - self.margin, footer_y + int(self.h * 0.07)), 
                     season_meaning, font=self.fonts['micro'], fill=self.COLORS['text_light'], anchor='rt')
    
    def draw_divider(self, draw, y, style='line'):
        """Draw elegant divider."""
        if style == 'line':
            draw.line([(self.margin, y), (self.w - self.margin, y)], 
                     fill=self.COLORS['divider'], width=1)
        elif style == 'dots':
            for x in range(self.margin, self.w - self.margin, 8):
                draw.ellipse([x-1, y-1, x+1, y+1], fill=self.COLORS['divider'])
    
    def draw_card_number(self, draw, number, x, y, size=None):
        """Draw elegant card number indicator."""
        if size is None:
            size = int(self.w * 0.04)
        
        # Circle background
        draw.ellipse([x-size, y-size, x+size, y+size], 
                    fill=self.COLORS['accent_gold'] + '40', outline=self.COLORS['accent_gold'])
        
        # Number
        draw.text((x, y), str(number), font=self.fonts['caption'], 
                 fill=self.COLORS['accent_gold'], anchor='mm')


class ImageLoader:
    """Handles image loading with proper sizing and fallbacks."""
    
    @staticmethod
    def load_and_fit(image_path_or_url, target_size, fallback_color='#E0D8C8'):
        """Load image and fit to target size with elegant fallback."""
        from PIL import ImageColor, ImageOps
        import requests
        
        try:
            from utils.image_loader import AdaptiveImageLoader
            loader = AdaptiveImageLoader()
            
            if image_path_or_url.startswith('http'):
                img = loader.from_url(image_path_or_url, target_size, resize=False)
            else:
                img = loader.from_file(image_path_or_url, target_size, resize=False)
            
            if img:
                # Fit to target size with elegant padding
                return ImageOps.pad(img.convert('RGB'), target_size, 
                                  color=ImageColor.getcolor(fallback_color, 'RGB'),
                                  method=Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")
        
        # Fallback - elegant placeholder
        bg = ImageColor.getcolor(fallback_color, 'RGB')
        img = Image.new('RGB', target_size, bg)
        draw = ImageDraw.Draw(img)
        
        # Draw subtle pattern
        for i in range(0, target_size[0], 20):
            draw.line([(i, 0), (i, target_size[1])], fill=bg + (30,), width=1)
        
        return img


def wrap_text(text, font, max_width):
    """Utility function for text wrapping."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = font.getbbox(test_line)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines
