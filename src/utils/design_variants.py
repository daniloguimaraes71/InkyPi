"""
Design variant system for Kansai Companion cards.
Defines multiple visual styles users can choose from in settings.
Colors blend with micro-season solar term palettes when available.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_VARIANT = "wa"

# Which color roles the seasonal palette can fill
SEASONAL_COLOR_MAP = {
    "bg": "bg",
    "accent": "accent",
    "accent_sage": "accent",
    "text_primary": "primary",
    "text_secondary": "secondary",
}


@dataclass
class DesignVariant:
    name: str
    label: str
    description: str
    heading_font: str
    body_font: str
    colors: Dict[str, str]
    divider_width: int = 1
    spacing_mult: float = 1.0
    divider_style: str = "line"
    border_style: str = "thin"
    section_style: str = "label"


VARIANTS: Dict[str, DesignVariant] = {
    "wa": DesignVariant(
        name="wa",
        label="Wa (和) - Classic",
        description="Traditional Japanese elegance with serif headings and warm gold accents",
        heading_font="Noto Serif JP",
        body_font="Noto Sans JP",
        colors={
            "bg": "#FAF8F5",
            "bg_alt": "#F5F7FA",
            "bg_dark": "#1A1A2E",
            "text_primary": "#2C2C2C",
            "text_secondary": "#555555",
            "text_light": "#666666",
            "accent": "#8B7355",
            "accent_alt": "#B87333",
            "accent_sage": "#7A8B6F",
            "divider": "#E0D8C8",
            "border": "#E0D8C8",
        },
        divider_width=1,
        spacing_mult=1.0,
    ),
    "zen": DesignVariant(
        name="zen",
        label="Zen (禅) - Minimal",
        description="Clean, airy minimalism with soft colors and abundant whitespace",
        heading_font="Noto Sans JP",
        body_font="Noto Sans JP",
        colors={
            "bg": "#FFFFFF",
            "bg_alt": "#FAFAFA",
            "bg_dark": "#2D2D3F",
            "text_primary": "#333333",
            "text_secondary": "#777777",
            "text_light": "#777777",
            "accent": "#9E9E9E",
            "accent_alt": "#BDBDBD",
            "accent_sage": "#A8B5A0",
            "divider": "#E8E8E8",
            "border": "#E0E0E0",
        },
        divider_width=1,
        spacing_mult=1.25,
    ),
    "ryoku": DesignVariant(
        name="ryoku",
        label="Ryoku (力) - Bold",
        description="Strong contrast, thick accents, and confident typography",
        heading_font="Noto Serif JP",
        body_font="Noto Sans JP",
        colors={
            "bg": "#F7F5F0",
            "bg_alt": "#EFEDE8",
            "bg_dark": "#1A1A1A",
            "text_primary": "#1A1A1A",
            "text_secondary": "#444444",
            "text_light": "#555555",
            "accent": "#C44545",
            "accent_alt": "#E06840",
            "accent_sage": "#5A7A5A",
            "divider": "#C0B8A8",
            "border": "#A09888",
        },
        divider_width=2,
        spacing_mult=0.9,
    ),
    "ima": DesignVariant(
        name="ima",
        label="Ima (今) - Modern",
        description="Contemporary sans-serif look with cool tones and clean geometry",
        heading_font="Noto Sans JP",
        body_font="Noto Sans JP",
        colors={
            "bg": "#F5F7FA",
            "bg_alt": "#EFF2F7",
            "bg_dark": "#1E2233",
            "text_primary": "#2C3E50",
            "text_secondary": "#607D8B",
            "text_light": "#607D8B",
            "accent": "#546E7A",
            "accent_alt": "#78909C",
            "accent_sage": "#66BB6A",
            "divider": "#CFD8DC",
            "border": "#B0BEC5",
        },
        divider_width=1,
        spacing_mult=1.1,
    ),
}

DESIGN_STYLE_CHOICES = [
    {"name": v.name, "label": v.label, "description": v.description}
    for v in VARIANTS.values()
]


def _blend_color(base_hex: str, seasonal_hex: str, weight: float = 0.5) -> str:
    """Blend two hex colors by weight (0 = all base, 1 = all seasonal)."""
    try:
        r1, g1, b1 = int(base_hex[1:3], 16), int(base_hex[3:5], 16), int(base_hex[5:7], 16)
        r2, g2, b2 = int(seasonal_hex[1:3], 16), int(seasonal_hex[3:5], 16), int(seasonal_hex[5:7], 16)
        r = int(r1 + (r2 - r1) * weight)
        g = int(g1 + (g2 - g1) * weight)
        b = int(b1 + (b2 - b1) * weight)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return base_hex


def get_variant(name: Optional[str], seasonal_palette: Optional[dict] = None) -> DesignVariant:
    """
    Get a design variant, optionally blended with a seasonal palette.
    The seasonal palette colors overlay onto the variant's base colors
    at a weight determined per color role.
    """
    if not name:
        name = DEFAULT_VARIANT
    variant = VARIANTS.get(name)
    if not variant:
        logger.warning(f"Unknown design variant '{name}', falling back to '{DEFAULT_VARIANT}'")
        variant = VARIANTS[DEFAULT_VARIANT]

    if not seasonal_palette:
        return variant

    # Blend seasonal colors into variant colors
    blended = dict(variant.colors)
    for role, palette_key in SEASONAL_COLOR_MAP.items():
        seasonal_color = seasonal_palette.get(palette_key)
        if seasonal_color and role in blended:
            # Stronger blend for bg and accent, lighter for text
            weight = 0.4 if role in ("bg", "bg_alt") else 0.3
            blended[role] = _blend_color(blended[role], seasonal_color, weight)

    # Create a copy of the variant with blended colors
    import copy
    result = copy.copy(variant)
    result.colors = blended
    return result
