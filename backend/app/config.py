import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").strip()
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "nvidia/Nemotron-3_5-Lightning").strip()
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter").strip()
CITY_NAME = os.getenv("CITY_NAME", "Nagpur").strip()
# Place search prefers results near the city centre and allows this far around it
# (Hingna, Kamptee, Butibori MIDC and so on).
CITY_LAT = float(os.getenv("CITY_LAT", "21.1458"))
CITY_LON = float(os.getenv("CITY_LON", "79.0882"))
SEARCH_RADIUS_KM = float(os.getenv("SEARCH_RADIUS_KM", "40"))
FORCE_MOCK = os.getenv("FORCE_MOCK", "0").strip() == "1"

MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"

HTTP_TIMEOUT = 12.0

# How old live data can get before it is labelled OUTDATED (minutes)
FRESH_MINUTES = 15
