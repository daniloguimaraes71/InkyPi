"""
Design variant system for Kansai Companion cards.
Defines multiple visual styles users can choose from in plugin settings.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_VARIANT = "wa"


@dataclass
class DesignVariant:
    name: str
    label: str
    description: str

    # Font families
    heading_font: str
    body_font: str

    # Color palette
    colors: Dict[str, str]

    # Divider
    divider_width: int = 1

    # Spacing multiplier (1.0 = default)
    spacing_mult: float = 1.0

    # Divider style: "line", "dots", "double"
    divider_style: str = "line"

    # Border style for image frames: "thin", "thick", "rounded", "none"
    border_style: str = "thin"

    # Whether to use small caps / decorative section labels
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
            "text_light": "#888888",
            "accent": "#8B7355",
            "accent_alt": "#B87333",
            "accent_sage": "#7A8B6F",
            "divider": "#E0D8C8",
            "border": "#E0D8C8",
        },
        divider_width=1,
        spacing_mult=1.0,
        divider_style="line",
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
            "text_light": "#AAAAAA",
            "accent": "#9E9E9E",
            "accent_alt": "#BDBDBD",
            "accent_sage": "#A8B5A0",
            "divider": "#E8E8E8",
            "border": "#E0E0E0",
        },
        divider_width=1,
        spacing_mult=1.25,
        divider_style="dots",
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
            "text_light": "#777777",
            "accent": "#C44545",
            "accent_alt": "#E06840",
            "accent_sage": "#5A7A5A",
            "divider": "#C0B8A8",
            "border": "#A09888",
        },
        divider_width=2,
        spacing_mult=0.9,
        divider_style="line",
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
            "text_light": "#90A4AE",
            "accent": "#546E7A",
            "accent_alt": "#78909C",
            "accent_sage": "#66BB6A",
            "divider": "#CFD8DC",
            "border": "#B0BEC5",
        },
        divider_width=1,
        spacing_mult=1.1,
        divider_style="line",
    ),
}

DESIGN_STYLE_CHOICES = [
    {"name": v.name, "label": v.label, "description": v.description}
    for v in VARIANTS.values()
]


def get_variant(name: Optional[str]) -> DesignVariant:
    if not name:
        name = DEFAULT_VARIANT
    variant = VARIANTS.get(name)
    if not variant:
        logger.warning(f"Unknown design variant '{name}', falling back to '{DEFAULT_VARIANT}'")
        variant = VARIANTS[DEFAULT_VARIANT]
    return variant


def get_setting_field(name: Optional[str]) -> str:
    return f"designStyle"
