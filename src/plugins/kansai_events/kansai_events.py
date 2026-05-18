import logging
import hashlib
import pytz
from datetime import datetime, timedelta
from plugins.base_plugin.base_plugin import BasePlugin
from utils.micro_season import get_full_season_info, get_seasonal_palette
from utils.wikipedia_images import get_wikipedia_image
from utils.app_utils import get_font
from utils.design_variants import get_variant
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Diverse, non-obvious Kansai attractions cycled deterministically per event+week
KANSAI_ATTRACTIONS = [
    "Byōdō-in", "Tōdai-ji", "Kinkaku-ji", "Ginkaku-ji", "Ryōan-ji",
    "Kiyomizu-dera", "Sanjūsangen-dō", "Fushimi_Inari-taisha", "Ninna-ji",
    "Tō-ji", "Daigo-ji", "Nijō_Castle", "Katsura_Imperial_Villa",
    "Shugakuin_Imperial_Villa", "Arashiyama", "Bamboo_forest_(Kyoto)",
    "Kibune_Shrine", "Kamigamo_Shrine", "Shimogamo_Shrine",
    "Osaka_Castle", "Sumiyoshi-taisha", "Shitennō-ji", "Dōtonbori",
    "Tsūtenkaku", "Osaka_Aquarium_Kaiyūkan", "Universal_Studios_Japan",
    "Abeno_Harukas", "Namba", "Umeda_Sky_Building",
    "Himeji_Castle", "Kōko-en", "Engyō-ji", "Mount_Shosha",
    "Nara_Park", "Kōfuku-ji", "Kasuga-taisha", "Yakushi-ji",
    "Tōshōdai-ji", "Mountain_Wu-tai", "Mount_Miwa",
    "Kobe_Port_Tower", "Kobe_Chinatown", "Arima_Onsen",
    "Mount_Rokkō", "Kobe_Luminarie", "Harborland",
    "Lake_Biwa", "Hikone_Castle", "Enryaku-ji", "Mii-dera",
    "Ishiyama-dera", "Chion-ji_(Kusatsu)",
    "Mount_Kōya", "Koyasan_Okunoin", "Kongōbu-ji",
    "Nachi_Falls", "Kumano_Nachi_Taisha", "Kumano_Hongū_Taisha",
    "Shirahama_Beach", "Wakayama_Castle",
    "Iga_Ueno_Castle", "Ise_Grand_Shrine", "Meiji_Shrine",
    "Amanohashidate", "Tottori_Sand_Dunes", "Izumo_Taisha",
    "Matsue_Castle", "Kurashiki", "Naoshima",
    "Takeda_Castle", "Yoshino,_Nara", "Mount_Yoshino",
    "Ōhara,_Okayama", "Koraku-en", "Okayama_Castle",
]

# Expanded region → location image mapping
REGION_IMAGES = {
    "大阪": "Osaka",
    "京都": "Kyoto",
    "神戸": "Kobe",
    "奈良": "Nara,_Japan",
    "滋賀": "Lake_Biwa",
    "和歌山": "Wakayama_Castle",
    "姫路": "Himeji_Castle",
    "兵庫": "Hyōgo_Prefecture",
    "奈良公園": "Nara_Park",
    "大阪城": "Osaka_Castle",
    "姫路城": "Himeji_Castle",
    "清水寺": "Kiyomizu-dera",
    "伏見稲荷": "Fushimi_Inari-taisha",
    "金閣寺": "Kinkaku-ji",
    "銀閣寺": "Ginkaku-ji",
    "東寺": "Tō-ji",
    "平等院": "Byōdō-in",
    "嵐山": "Arashiyama",
    "道頓堀": "Dōtonbori",
    "通天閣": "Tsūtenkaku",
    "有馬温泉": "Arima_Onsen",
    "六甲山": "Mount_Rokkō",
    "神戸港": "Kobe_Port_Tower",
    "琵琶湖": "Lake_Biwa",
    "彦根城": "Hikone_Castle",
    "高野山": "Mount_Kōya",
    "那智": "Nachi_Falls",
    "熊野": "Kumano_Nachi_Taisha",
    "白浜": "Shirahama_Beach",
    "梅田": "Umeda_Sky_Building",
    "天保山": "Osaka_Aquarium_Kaiyūkan",
}

IMAGE_SEARCH = {
    "桜": "Cherry_blossom",
    "花見": "Hanami",
    "祭": "Matsuri",
    "花火": "Fireworks",
    "紅葉": "Maple",
    "灯": "Lantern",
    "梅": "Prunus_mume",
    "月": "Moon",
    "七夕": "Tanabata",
    "雪": "Snow",
    "収穫": "Harvest",
    "展示": "Exhibition",
    "コンサート": "Concert",
    "ライブ": "Concert",
    "展覧会": "Exhibition",
    "フェス": "Music_festival",
    "マルシェ": "Farmers'_market",
    "花": "Flower",
    "灯り": "Illumination",
    "イルミ": "Illumination",
    "花火大会": "Fireworks",
    "縁日": "Matsuri",
    "神輿": "Mikoshi",
    "太鼓": "Taiko",
    "茶会": "Japanese_tea_ceremony",
    "着物": "Kimono",
    "能": "Noh",
    "狂言": "Kyōgen",
    "歌舞伎": "Kabuki",
    "陶器": "Japanese_pottery",
    "工芸": "Japanese_craft",
    "美術": "Art_museum",
    "写経": "Shakyo",
    "座禅": "Zazen",
    "寺": "Buddhist_temple_in_Japan",
    "神社": "Shinto_shrine",
    "城": "Japanese_castle",
    "園": "Japanese_garden",
    "温泉": "Onsen",
    "ビール": "Beer",
    "ワイン": "Wine",
    "食": "Japanese_cuisine",
    "海": "Sea",
    "山": "Mountain",
    "川": "River",
    "湖": "Lake",
}


class KansaiEvents(BasePlugin):
    def generate_image(self, settings, device_config):
        timezone = device_config.get_config("timezone", default="Asia/Tokyo")
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        dimensions = device_config.get_resolution()
        orientation = device_config.get_config("orientation", "horizontal")

        season_info = get_full_season_info(now)
        seasonal_palette = get_seasonal_palette(now)
        v = get_variant(device_config.get_config("design_style"), seasonal_palette)

        month = now.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "autumn"
        else:
            season = "winter"

        events = self._fetch_kansai_events(settings, now)
        weekend_date = self._get_upcoming_weekend(now)

        event_images = []
        for ev in events[:3]:
            img = self._get_event_image(ev)
            event_images.append(img)

        event_image_data_uris = [self.image_to_data_uri(img) for img in event_images]

        try:
            dimensions_for_render = device_config.get_resolution()
            if orientation == "vertical":
                dimensions_for_render = dimensions_for_render[::-1]

            template_params = {
                "palette": seasonal_palette,
                "season_info": season_info,
                "events": events[:3],
                "weekend_date": weekend_date,
                "event_images": event_image_data_uris,
                "season_label": f"{season_info['micro_season']['kanji']} - {season_info['micro_season']['english']}" if season_info else "",
                "plugin_settings": settings,
                "design_variant": {
                    "name": v.name,
                    "colors": v.colors,
                    "heading_font": v.heading_font,
                    "body_font": v.body_font,
                    "divider_width": v.divider_width,
                },
            }

            image = self.render_image(dimensions_for_render, "kansai_events.html", "kansai_events.css", template_params)
            if image:
                return image
        except Exception as e:
            logger.warning(f"HTML render failed, falling back to PIL: {e}")

        return self._draw_card_pil(dimensions, orientation, events, season_info, settings, now, weekend_date, event_images, v)

    def _draw_card_pil(self, dimensions, orientation, events, season_info, settings, now, weekend_date, event_images, v):
        """Kansai events card with photo strip."""
        w, h = dimensions
        if orientation == 'vertical':
            w, h = h, w

        C = v.colors
        sm = v.spacing_mult

        img = Image.new('RGB', (w, h), C['bg'])
        draw = ImageDraw.Draw(img)

        px = int(w * 0.04 * sm)
        py = int(h * 0.06 * sm)
        list_w = int(w * 0.55)

        f_title = get_font(v.heading_font, int(w * 0.045))
        f_sub = get_font(v.body_font, int(w * 0.016))
        f_name = get_font(v.heading_font, int(w * 0.022))
        f_desc = get_font(v.body_font, int(w * 0.016))
        f_loc = get_font(v.body_font, int(w * 0.014))
        f_ms = get_font(v.heading_font, int(w * 0.016))
        f_ms_en = get_font(v.body_font, int(w * 0.012))

        draw.text((px, py), "今週末のイベント", font=f_title, fill=C['text_primary'])
        if weekend_date:
            draw.text((px, py + int(h * 0.06 * sm)), weekend_date, font=f_sub, fill=C['text_light'])

        ev_start = py + int(h * 0.12 * sm)
        ev_h = int(h * 0.22)
        for i, event in enumerate(events[:3]):
            y = ev_start + i * (ev_h + int(h * 0.02))
            name = event.get("name", event.get("title", "Untitled"))
            desc = event.get("description", event.get("desc", ""))
            location = event.get("location", event.get("loc", ""))

            if i < len(event_images) and event_images[i]:
                thumb_w = int(w * 0.08)
                thumb_h = ev_h - int(h * 0.04)
                tx = px
                ty = y + int(h * 0.02)
                try:
                    thumb = event_images[i].resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    img.paste(thumb, (tx, ty))
                    draw = ImageDraw.Draw(img)
                    draw.rectangle([tx-1, ty-1, tx+thumb_w+1, ty+thumb_h+1], outline=C['border'], width=v.divider_width)
                except:
                    pass

            name_x = px + int(w * 0.1)
            name_y = y
            tw_max = list_w - int(w * 0.12)
            draw.text((name_x, name_y), name, font=f_name, fill=C['text_primary'])
            if desc:
                draw.text((name_x, name_y + int(h * 0.3 * sm)), desc, font=f_desc, fill=C['text_secondary'])
            if location:
                draw.text((name_x, name_y + int(h * 0.55 * sm)), f"場所: {location}", font=f_loc, fill=C['text_light'])

            if i < 2:
                div_y = y + ev_h + int(h * 0.005)
                draw.line([(px, div_y), (list_w - int(w * 0.02), div_y)], fill=C['divider'], width=v.divider_width)

        if season_info:
            ms_x = list_w - int(w * 0.02)
            ms_y = h - int(h * 0.05 * sm)
            k = f"時候: {season_info['micro_season']['kanji']}"
            bbox = draw.textbbox((0, 0), k, font=f_ms)
            draw.text((ms_x - (bbox[2]-bbox[0]), ms_y), k, font=f_ms, fill=C['accent'])
            e = season_info['micro_season']['english']
            bbox_e = draw.textbbox((0, 0), e, font=f_ms_en)
            draw.text((ms_x - (bbox_e[2]-bbox_e[0]), ms_y + int(h * 0.02 * sm)), e, font=f_ms_en, fill=C['text_light'])

        return img

    def _get_upcoming_weekend(self, now):
        days_ahead = 5 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        saturday = now + timedelta(days=days_ahead)
        sunday = saturday + timedelta(days=1)
        return f"{saturday.strftime('%m/%d')}（土）〜 {sunday.strftime('%m/%d')}（日）"

    def _fetch_kansai_events(self, settings, now):
        try:
            from utils.kansai_news import fetch_kansai_events, get_kansai_events_list
            events = fetch_kansai_events()
            if events:
                return events
            return get_kansai_events_list(now, count=3)
        except Exception as e:
            logger.warning(f"Failed to fetch Kansai events: {e}")
            return []

    def _get_event_image(self, event):
        """Fetch a relevant, non-obvious image for an event.
        Uses deterministic selection per event+week for natural variety.
        """
        try:
            name = event.get("name", "")
            location = event.get("location", "")
            wiki_keyword = event.get("wiki", "")

            # Priority 1: Exact location mapping from event name or location
            for region, keyword in REGION_IMAGES.items():
                if region in location or region in name:
                    img = get_wikipedia_image(keyword, (200, 200))
                    if img:
                        return img

            # Priority 2: Keyword match from event name
            sorted_keywords = sorted(IMAGE_SEARCH.items(), key=lambda x: -len(x[0]))
            for kword, title in sorted_keywords:
                if kword in name:
                    img = get_wikipedia_image(title, (200, 200))
                    if img:
                        return img

            # Priority 3: Try wiki field directly
            if wiki_keyword:
                img = get_wikipedia_image(wiki_keyword, (200, 200))
                if img:
                    return img

            # Priority 4: Deterministic selection from Kansai attractions pool
            # Uses event name + ISO week number so same event gets different
            # images on different weeks, and different events get different images
            now = datetime.now()
            week_seed = now.isocalendar()[1]
            seed_str = f"{name}_{week_seed}"
            hash_val = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
            idx = hash_val % len(KANSAI_ATTRACTIONS)
            candidate = KANSAI_ATTRACTIONS[idx]

            img = get_wikipedia_image(candidate, (200, 200))
            if img:
                return img

            # Priority 5: Try 3 more candidates from the pool around the hash
            for offset in range(1, 4):
                alt_idx = (idx + offset * 37) % len(KANSAI_ATTRACTIONS)
                img = get_wikipedia_image(KANSAI_ATTRACTIONS[alt_idx], (200, 200))
                if img:
                    return img

            return None

        except Exception as e:
            logger.warning(f"Failed to get event image: {e}")
            return None

    def _generate_location_placeholder(self, location, event_type, size):
        """Generate a colored placeholder image with location name."""
        w, h = size
        img = Image.new('RGB', (w, h), '#E8E4DC')
        draw = ImageDraw.Draw(img)

        for y in range(h):
            c = int(232 * (1 - y / h * 0.1))
            draw.line([(0, y), (w, y)], fill=(c, c - 6, c - 14))

        f_loc = get_font("Noto Serif JP", int(w * 0.18))
        f_type = get_font("Noto Sans JP", int(w * 0.12))

        loc_text = location if location else "関西"
        bbox = draw.textbbox((0, 0), loc_text, font=f_loc)
        x = (w - (bbox[2]-bbox[0])) // 2
        y = (h - (bbox[3]-bbox[1])) // 2 - int(h * 0.1)
        draw.text((x, y), loc_text, font=f_loc, fill='#8B7355')

        bbox2 = draw.textbbox((0, 0), event_type, font=f_type)
        draw.text(((w - (bbox2[2]-bbox2[0])) // 2, y + (bbox[3]-bbox[1]) + int(h * 0.05)), event_type, font=f_type, fill='#AAAAAA')

        return img
