"""
Wikipedia image fetcher for Kansai Companion.
Fetches relevant images from Wikipedia articles based on keywords.
Uses the same pattern as the wpotd plugin.
"""
import logging
import time
from io import BytesIO
from PIL import Image
from utils.http_client import get_http_session
from utils.image_loader import AdaptiveImageLoader

logger = logging.getLogger(__name__)

# Cache for fetched images
_image_cache = {}

# Rate limiting
_last_request_time = 0
_MIN_REQUEST_INTERVAL = 1.0

# Wikipedia API
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {'User-Agent': 'InkyPi/1.0 (https://github.com/fatihak/InkyPi/)'}

# Curated Wikipedia article mappings
ARTICLE_MAPPINGS = {
    # Flowers
    "桜": "Cherry_blossom",
    "梅": "Prunus_mume",
    "藤": "Wisteria",
    "菜の花": "Rapeseed",
    "紫陽花": "Hydrangea",
    "蓮": "Nelumbo_nucifera",
    "向日葵": "Sunflower",
    "朝顔": "Ipomoea_nil",
    "萩": "Lespedeza",
    "菊": "Chrysanthemum",
    "紅葉": "Maple",
    "秋桜": "Cosmos_(plant)",
    "椿": "Camellia_japonica",
    "水仙": "Narcissus_(plant)",
    "山茶花": "Camellia_sasanqua",
    
    # Kansai locations
    "大阪城": "Osaka_Castle",
    "奈良公園": "Nara_Park",
    "清水寺": "Kiyomizu-dera",
    "祇園": "Gion",
    "箕面": "Minoh,_Osaka",
    "伏見稲荷": "Fushimi_Inari-taisha",
    "姫路城": "Himeji_Castle",
    "有馬温泉": "Arima_Onsen",
    "梅田スカイビル": "Umeda_Sky_Building",
    "天神祭": "Tenjin_Matsuri",
    "神戸ルミナリー": "Kobe_Luminarie",
    "好古園": "Koko-en",
    "京都": "Kyoto",
    "大阪": "Osaka",
    "神戸": "Kobe",
    "奈良": "Nara_(city)",
    "須磨海水浴場": "Suma_Beach",
    "大阪": "Osaka",
    
    # Food - Japanese dishes
    "おにぎり": "Onigiri",
    "味噌汁": "Miso_soup",
    "寿司": "Sushi",
    "ラーメン": "Ramen",
    "たこ焼き": "Takoyaki",
    "お好み焼き": "Okonomiyaki",
    "カレー": "Curry",
    "抹茶": "Matcha",
    "珈琲": "Coffee",
    "パスタ": "Pasta",
    "サラダ": "Salad",
    "フレンチトースト": "French_toast",
    "ナン": "Naan",
    "お寿司": "Sushi",
    "おでん": "Oden",
    "天ぷら": "Tempura",
    "うな丼": "Unadon",
    "親子丼": "Oyakodon",
    "カレーライス": "Japanese_curry",
    "とんかつ": "Tonkatsu",
    "納豆": "Natto",
    "茶碗蒸し": "Chawanmushi",
    "サンドイッチ": "Sandwich",
    "ピザ": "Pizza",
    "ハンバーグ": "Hamburg_steak",
    "グラタン": "Gratin",
    "オムライス": "Omurice",
    "リゾット": "Risotto",
    "タコス": "Taco",
    "フォー": "Pho",
    "豆腐": "Tofu",
    "ヨーグルト": "Yogurt",
    "雑炊": "Zōsui",
    "枝豆": "Edamame",
    "すき焼き": "Sukiyaki",
    "しゃぶしゃぶ": "Shabu-shabu",
    "鍋": "Hot_pot",
    "焼き芋": "Roasted_sweet_potato",
    "かぼちゃ": "Kabocha",
    "大根": "Daikon",
    "お汁粉": "Shiruko",
    "ぜんざい": "Zenzai",
    
    # General
    "月": "Moon",
    "夕日": "Sunset",
    "朝日": "Sunrise",
}


def get_wikipedia_image(keyword, target_size=(400, 300)):
    """Fetch an image from Wikipedia based on a keyword."""
    cache_key = f"{keyword}_{target_size[0]}x{target_size[1]}"
    if cache_key in _image_cache:
        return _image_cache[cache_key]
    
    try:
        # Check if we have a curated mapping
        article_title = ARTICLE_MAPPINGS.get(keyword, keyword)
        
        # Get image URL from Wikipedia
        image_url = _get_article_image_url(article_title)
        
        if image_url:
            img = _download_image(image_url, target_size)
            if img:
                _image_cache[cache_key] = img
                return img
        
        logger.warning(f"No image found for keyword: {keyword}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching Wikipedia image for {keyword}: {e}")
        return None


JA_WIKIPEDIA_API = "https://ja.wikipedia.org/w/api.php"

def _get_article_image_url(article_title):
    """Get the main image URL from a Wikipedia article.
    Tries English Wikipedia first, then Japanese Wikipedia as fallback.
    """
    result = _query_wikipedia(article_title, WIKIPEDIA_API)
    if result:
        return result
    # Fallback: try Japanese Wikipedia
    result = _query_wikipedia(article_title, JA_WIKIPEDIA_API)
    if result:
        return result
    return None


def _query_wikipedia(article_title, api_url):
    """Query a Wikipedia API for article images."""
    global _last_request_time
    
    try:
        # Rate limiting
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        
        session = get_http_session()
        
        params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "titles": article_title,
            "pithumbsize": 800
        }
        
        _last_request_time = time.time()
        response = session.get(api_url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            thumbnail = page.get("thumbnail", {})
            if thumbnail.get("source"):
                return thumbnail["source"]
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to get article image for {article_title} from {api_url}: {e}")
        return None


def _download_image(url, target_size):
    """Download and resize an image."""
    global _last_request_time
    
    try:
        # Rate limiting
        elapsed = time.time() - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        
        # Use adaptive loader for memory-efficient processing
        loader = AdaptiveImageLoader()
        _last_request_time = time.time()
        
        img = loader.from_url(url, target_size, timeout_ms=15000, headers=HEADERS)
        return img
        
    except Exception as e:
        logger.warning(f"Failed to download image from {url}: {e}")
        return None


def get_seasonal_flower_image(flower_name, target_size=(300, 400)):
    """Get an image of a seasonal flower."""
    return get_wikipedia_image(flower_name, target_size)


def get_kansai_location_image(location_name, target_size=(400, 300)):
    """Get an image of a Kansai location."""
    return get_wikipedia_image(location_name, target_size)


def get_food_image(food_name, target_size=(300, 300)):
    """Get an image of Japanese food."""
    return get_wikipedia_image(food_name, target_size)
