import logging
import os
from utils.app_utils import resolve_path, get_fonts
from utils.image_utils import take_screenshot_html
from utils.image_loader import AdaptiveImageLoader
from utils.design_variants import DESIGN_STYLE_CHOICES, get_variant
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import asyncio
import base64

logger = logging.getLogger(__name__)

STATIC_DIR = resolve_path("static")
PLUGINS_DIR = resolve_path("plugins")
BASE_PLUGIN_DIR =  os.path.join(PLUGINS_DIR, "base_plugin")
BASE_PLUGIN_RENDER_DIR = os.path.join(BASE_PLUGIN_DIR, "render")

FRAME_STYLES = [
    {
        "name": "None",
        "icon": "frames/blank.png"
    },
    {
        "name": "Corner",
        "icon": "frames/corner.png"
    },
    {
        "name": "Top and Bottom",
        "icon": "frames/top_and_bottom.png"
    },
    {
        "name": "Rectangle",
        "icon": "frames/rectangle.png"
    }
]

class BasePlugin:
    """Base class for all plugins."""
    def __init__(self, config, **dependencies):
        self.config = config

        # Initialize adaptive image loader for device-aware image processing
        self.image_loader = AdaptiveImageLoader()

        self.render_dir = self.get_plugin_dir("render")
        if os.path.exists(self.render_dir):
            # instantiate jinja2 env with base plugin and current plugin render directories
            loader = FileSystemLoader([self.render_dir, BASE_PLUGIN_RENDER_DIR])
            self.env = Environment(
                loader=loader,
                autoescape=select_autoescape(['html', 'xml'])
            )

    def generate_image(self, settings, device_config):
        raise NotImplementedError("generate_image must be implemented by subclasses")

    def cleanup(self, settings):
        """Optional cleanup method that plugins can override to delete associated resources.

        Called when a plugin instance is deleted. Plugins should override this to clean up
        any files, external resources, or other data associated with the plugin instance.

        Args:
            settings: The plugin instance's settings dict, which may contain file paths or other resources
        """
        pass  # Default implementation does nothing

    def get_design_variant(self, settings):
        return get_variant(settings.get("designStyle"))

    def get_plugin_id(self):
        return self.config.get("id")

    def get_plugin_dir(self, path=None):
        plugin_dir = os.path.join(PLUGINS_DIR, self.get_plugin_id())
        if path:
            plugin_dir = os.path.join(plugin_dir, path)
        return plugin_dir

    def generate_settings_template(self):
        template_params = {"settings_template": "base_plugin/settings.html"}

        settings_path = self.get_plugin_dir("settings.html")
        if Path(settings_path).is_file():
            template_params["settings_template"] = f"{self.get_plugin_id()}/settings.html"

        template_params['frame_styles'] = FRAME_STYLES
        template_params['design_styles'] = DESIGN_STYLE_CHOICES
        return template_params

    def image_to_data_uri(self, img):
        """Convert a PIL Image to a base64 data URI for HTML embedding."""
        if img is None:
            return None
        from io import BytesIO
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    def render_image(self, dimensions, html_file, css_file=None, template_params={}):
        # load the base plugin and current plugin css files
        css_files = [
            os.path.join(BASE_PLUGIN_RENDER_DIR, "plugin.css"),
            os.path.join(BASE_PLUGIN_RENDER_DIR, "design-system.css")
        ]
        if css_file:
            plugin_css = os.path.join(self.render_dir, css_file)
            css_files.append(plugin_css)

        template_params["style_sheets"] = css_files
        template_params["width"] = dimensions[0]
        template_params["height"] = dimensions[1]
        template_params["font_faces"] = get_fonts()
        template_params["static_dir"] = STATIC_DIR

        # Use design variant passed from plugin, or derive from settings
        if "design_variant" not in template_params:
            ps = template_params.get("plugin_settings", {})
            if isinstance(ps, dict):
                variant = get_variant(ps.get("designStyle"))
            else:
                variant = get_variant(None)
            template_params["design_variant"] = {
                "name": variant.name,
                "colors": variant.colors,
                "heading_font": variant.heading_font,
                "body_font": variant.body_font,
                "divider_width": variant.divider_width,
            }

        # Provide default plugin_settings if not present
        if "plugin_settings" not in template_params:
            template_params["plugin_settings"] = {
                "selectedFrame": "None",
                "backgroundOption": "color",
                "backgroundColor": "#FAF8F5",
                "textColor": "#2C2C2C",
                "margin": 0,
                "topMargin": 0,
                "bottomMargin": 0,
                "leftMargin": 0,
                "rightMargin": 0,
            }

        # load and render the given html template
        template = self.env.get_template(html_file)
        rendered_html = template.render(template_params)

        return take_screenshot_html(rendered_html, dimensions)
