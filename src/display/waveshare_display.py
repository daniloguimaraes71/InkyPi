import inspect
import importlib
import logging
import sys

from display.abstract_display import AbstractDisplay
from PIL import Image, ImageEnhance
from pathlib import Path
from plugins.plugin_registry import get_plugin_instance

logger = logging.getLogger(__name__)


def split_image_for_bi_color_epd(image):
    """
    Convert image into two 1-bit layers for bi-color (black and red) e-paper displays.
    """
    black = (0, 0, 0)
    white = (255, 255, 255)
    red = (255, 0, 0)

    palette_data = [*black, *white, *red]
    palette_img = Image.new('P', (1, 1))
    palette_img.putpalette(palette_data)

    indexed_img = image.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)
    black_layer = indexed_img.point(lambda p: 0 if p == 0 else 1, mode='1')
    red_layer = indexed_img.point(lambda p: 0 if p == 2 else 1, mode='1')
    return black_layer, red_layer


class WaveshareDisplay(AbstractDisplay):
    """
    Handles Waveshare e-paper display dynamically based on device type.

    This class loads the appropriate display driver dynamically based on the 
    `display_type` specified in the device configuration, allowing support for 
    multiple Waveshare EPD models.  

    The module drivers are in display.waveshare_epd.
    """

    def initialize_display(self):
        
        """
        Initializes the Waveshare display device.

        Retrieves the display type from the device configuration and dynamically 
        loads the corresponding Waveshare EPD driver from display.waveshare_epd.

        Raises:
            ValueError: If `display_type` is missing or the specified module is 
                        not found.
        """
        
        logger.info("Initializing Waveshare display")

        # get the device type which should be the model number of the device.
        display_type = self.device_config.get_config("display_type")  
        logger.info(f"Loading EPD display for {display_type} display")

        if not display_type:
            raise ValueError("Waveshare driver but 'display_type' not specified in configuration.")

        # Construct module path dynamically - e.g. "display.waveshare_epd.epd7in3e"
        module_name = f"display.waveshare_epd.{display_type}" 

        # Workaround for some Waveshare drivers using 'import epdconfig' causing import errors
        epd_dir = Path(__file__).parent / "waveshare_epd"
        if str(epd_dir) not in sys.path:
            sys.path.insert(0, str(epd_dir))

        try:
            # Dynamically load module
            epd_module = importlib.import_module(module_name)  
            self.epd_display = epd_module.EPD()
            # Workaround for init functions with inconsistent casing
            self.epd_display_init = getattr(self.epd_display, "Init", getattr(self.epd_display, "init", None))

            if not callable(self.epd_display_init):
                raise AttributeError("No Init/init method found")

            self.epd_display_init()

            display_args_spec = inspect.getfullargspec(self.epd_display.display)
        except ModuleNotFoundError:
            raise ValueError(f"Unsupported Waveshare display type: {display_type}")
        except AttributeError:
            raise ValueError(f"Display does not support required methods: {display_type}")

        self.bi_color_display = len(display_args_spec.args) > 2

        # Patch getbuffer for 7-color displays to use correct palette + Floyd-Steinberg dithering
        if not self.bi_color_display and hasattr(self.epd_display, 'YELLOW') and hasattr(self.epd_display, 'GREEN'):
            self._patch_getbuffer_for_7color()

        # update the resolution directly from the loaded device context
        if not self.device_config.get_config("resolution"):
            w, h = int(self.epd_display.width), int(self.epd_display.height)
            resolution = [w, h] if w >= h else [h, w]
            self.device_config.update_value(
                "resolution",
                resolution,
                write=True)


    def _patch_getbuffer_for_7color(self):
        """
        Patch the EPD driver's getbuffer to implement a full
        epdoptimize-style pipeline for optimal e-ink color reproduction:

          1. S-curve tone mapping — boosts midtones while gently compressing
             shadows/highlights, keeping details across the narrow e-ink range.
          2. Saturation boost — pushes image colors toward palette primaries
             so they survive the reduction to only 7 palette entries.
          3. Dither against calibrated (measured) palette colors — the
             real pigment appearance is much more muted than pure sRGB, so
             matching perceptually produces far richer results.

        Palette values come from the E Ink Gallery / AcEP measured palette
        (same 7-colour chemistry as Waveshare 7-colour displays).
        """
        # Calibrated palette — measured display appearance, not sRGB.
        # Dithering against these perceptually-accurate colours means the
        # error-diffusion algorithm makes the right trade-offs.
        CALIBRATED = [
            (25, 30, 33),     # 0: Black   #191E21
            (241, 241, 241),  # 1: White   #F1F1F1
            (243, 207, 17),   # 2: Yellow  #F3CF11
            (210, 14, 19),    # 3: Red     #D20E13
            (184, 94, 28),    # 4: Orange  #B85E1C
            (49, 49, 143),    # 5: Blue    #31318F
            (83, 164, 40),    # 6: Green   #53A428
        ]

        epd = self.epd_display
        width, height = epd.width, epd.height

        pal_img = Image.new('P', (1, 1))
        pal_data = []
        for c in CALIBRATED:
            pal_data.extend(c)
        pal_img.putpalette(pal_data + [0, 0, 0] * 249)

        def _s_curve_lut(strength=0.9, shadow_boost=0.0,
                         highlight_compress=1.5, midpoint=0.5):
            lut = []
            for i in range(256):
                n = i / 255.0
                if n <= midpoint:
                    sv = n / midpoint if midpoint > 0 else 0
                    result = (sv ** (1 - strength * shadow_boost)) * midpoint
                else:
                    hv = (n - midpoint) / (1 - midpoint) if midpoint < 1 else 0
                    result = (midpoint +
                              (hv ** (1 + strength * highlight_compress))
                              * (1 - midpoint))
                lut.append(max(0, min(255, int(result * 255 + 0.5))))
            return lut
        SCURVE_LUT = _s_curve_lut()

        def getbuffer_with_dithering(image):
            imwidth, imheight = image.size
            if imwidth == width and imheight == height:
                image_temp = image
            elif imwidth == height and imheight == width:
                image_temp = image.rotate(90, expand=True)
            else:
                logger.warning(
                    "Invalid image dimensions: %d x %d, expected %d x %d",
                    imwidth, imheight, width, height,
                )
                image_temp = image

            image_temp = image_temp.convert('RGB')

            # 1. S-curve tone mapping (per-channel) — preserves detail
            #    across the e-ink panel's narrow dynamic range.
            image_temp = image_temp.point(SCURVE_LUT)

            # 2. Saturation boost — pushes colours toward palette primaries.
            image_temp = ImageEnhance.Color(image_temp).enhance(1.3)

            # 3. Quantize to calibrated palette with Floyd-Steinberg
            #    dithering.  Because we matched against the actual muted
            #    pigment appearance, the error diffusion produces
            #    perceptually correct colour mixtures.
            image_7color = image_temp.quantize(
                palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG
            )
            buf_7color = bytearray(image_7color.tobytes('raw'))

            buf = bytearray(width * height // 2)
            for i in range(0, len(buf_7color), 2):
                buf[i // 2] = (buf_7color[i] << 4) | buf_7color[i + 1]

            return buf

        epd.getbuffer = getbuffer_with_dithering
        logger.info("Patched getbuffer with calibrated 7-color palette + "
                     "S-curve tone mapping + Floyd-Steinberg dithering")

    def display_image(self, image, image_settings=[]):
        
        """
        Displays an image on the Waveshare display.

        The image has been processed by adjusting orientation, resizing, and converting it
        into the buffer format required for e-paper rendering.

        Args:
            image (PIL.Image): The image to be displayed.
            image_settings (list, optional): Additional settings to modify image rendering.

        Raises:
            ValueError: If no image is provided.
        """

        logger.info("Displaying image to Waveshare display.")
        if not image:
            raise ValueError(f"No image provided.")

        try:
            self._display_image(image)
        except OSError:
            logger.warning("SPI error on display, reinitializing and retrying...")
            self.initialize_display()
            self._display_image(image)

    def _display_image(self, image):
        self.epd_display_init()
        # Power off after init so display() writes data in powered-off state
        # (required by some Waveshare display controllers to avoid frame buffer corruption)
        # Skip Clear() to avoid an unnecessary full-refresh cycle
        self.epd_display.send_command(0x02)
        self.epd_display.send_data(0x00)
        self.epd_display.ReadBusyH()
        if not self.bi_color_display:
            self.epd_display.display(self.epd_display.getbuffer(image))
        else:
            black_layer, red_layer = split_image_for_bi_color_epd(image)
            self.epd_display.display(
                self.epd_display.getbuffer(black_layer),
                self.epd_display.getbuffer(red_layer),
            )
        logger.info("Putting Waveshare display into sleep mode for power saving.")
        self.epd_display.sleep()
