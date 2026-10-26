import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").strip()
# Exact model ID from the Token Factory catalog; the AI estimate stays off until it is set
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "").strip()
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "").strip()
MAPILLARY_TOKEN = os.getenv("MAPILLARY_TOKEN", "").strip()
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter").strip()
# Tried in order; the public Overpass servers are often busy
OVERPASS_URLS = [OVERPASS_URL, "https://overpass.kumi.systems/api/interpreter"]
# Shop and place lists change slowly, so they count as fresh for a day (traffic and weather use FRESH_MINUTES)
PLACES_FRESH_MINUTES = 24 * 60
CITY_NAME = os.getenv("CITY_NAME", "Nagpur").strip()
# Place search prefers results near the city centre and allows this far around it
# (Hingna, Kamptee, Butibori MIDC and so on).
CITY_LAT = float(os.getenv("CITY_LAT", "21.1458"))
CITY_LON = float(os.getenv("CITY_LON", "79.0882"))
SEARCH_RADIUS_KM = float(os.getenv("SEARCH_RADIUS_KM", "40"))
FORCE_MOCK = os.getenv("FORCE_MOCK", "0").strip() == "1"

MOCK_DATA_PATH = BASE_DIR / "data" / "mock_data.json"

HTTP_TIMEOUT = 12.0
USER_AGENT = "NISAARTHI/0.1 (night-safety route app, hackathon)"

# How old live data can get before it is labelled OUTDATED (minutes)
FRESH_MINUTES = 15
