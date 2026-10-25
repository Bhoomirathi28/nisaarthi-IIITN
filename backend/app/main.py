from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import io
import json

from . import config, planner, users
from .vision import street_check
from .services import mockdata

app = FastAPI(title="NISAARTHI API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Point(BaseModel):
    lat: float
    lon: float


class PlanRequest(BaseModel):
    origin: Point
    destination: Point
    stops: List[Point] = Field(default_factory=list, max_length=3)  # optional stops, in order
    departure: Optional[str] = None  # ISO time the shift ends; defaults to now
    deadline: Optional[str] = None   # ISO time the worker must reach home by
    mode: Literal["walk", "motorcycle", "drive"] = "walk"


def _parse_time(value, fallback=None):
    if not value:
        return fallback
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"Bad time: {value}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
    return dt


class ContactIn(BaseModel):
    name: str
    phone: str


class SignUp(BaseModel):
    name: str
    phone: str
    language: str = "en"
    contacts: List[ContactIn]


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None


class ContactsUpdate(BaseModel):
    contacts: List[ContactIn]


def db():
    conn = users.connect()
    try:
        yield conn
    finally:
        conn.close()


def current_user(authorization: Optional[str] = Header(None), conn=Depends(db)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = users.user_for_token(conn, token)
    if not user:
        raise HTTPException(401, "not_signed_up")
    return user


def _bad(e):
    return HTTPException(422, str(e))


@app.post("/users", status_code=201)
def sign_up(body: SignUp, conn=Depends(db)):
    try:
        user, token = users.create_user(conn, body.name, body.phone, body.language,
                                        [c.model_dump() for c in body.contacts])
    except users.InvalidInput as e:
        raise _bad(e)
    return {"user": user, "token": token}


@app.get("/users/me")
def me(user=Depends(current_user)):
    return user


@app.patch("/users/me")
def update_me(body: ProfileUpdate, user=Depends(current_user), conn=Depends(db)):
    try:
        return users.update_profile(conn, user["id"], body.name, body.language)
    except users.InvalidInput as e:
        raise _bad(e)


@app.put("/users/me/contacts")
def update_contacts(body: ContactsUpdate, user=Depends(current_user), conn=Depends(db)):
    try:
        return {"contacts": users.replace_contacts(conn, user["id"], [c.model_dump() for c in body.contacts])}
    except users.InvalidInput as e:
        raise _bad(e)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "force_mock": config.FORCE_MOCK,
        "sources": {
            "geoapify": bool(config.GEOAPIFY_API_KEY),
            "tavily": bool(config.TAVILY_API_KEY),
            "nebius": bool(config.NEBIUS_API_KEY),
            "overpass": True,
            "open_meteo": True,
        },
    }


@app.get("/demo")
def demo():
    return mockdata.demo_trip()


@app.post("/plan")
async def plan(req: PlanRequest):
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    departure = _parse_time(req.departure, now)
    deadline = _parse_time(req.deadline)
    if deadline and deadline <= departure:
        deadline += timedelta(days=1)  # "reach by 03:00" after a 23:30 shift end
    return await planner.plan((req.origin.lat, req.origin.lon), (req.destination.lat, req.destination.lon),
                              departure, deadline, req.mode, [(s.lat, s.lon) for s in req.stops])


@app.get("/places/search")
async def places_search(text: str, lat: Optional[float] = None, lon: Optional[float] = None):
    """Autocomplete for the trip page, around the city (see SEARCH_RADIUS_KM)."""
    if len(text.strip()) < 3:
        return {"results": [], "state": "none"}
    near = (lat, lon) if lat is not None and lon is not None else None
    return await planner.search_places(text, near)


@app.get("/help/nearby")
async def help_nearby(lat: float, lon: float):
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    return await planner.help_nearby(lat, lon, now)


# ---- Street check (image processing; used by Rider Eyes in Phase 6) ----

STREET_INDEX = config.BASE_DIR / "data" / "street_index.json"


@app.post("/street-check")
async def street_check_image(image: UploadFile = File(...)):
    """Score how lit and active a street looks in one photo or CCTV frame."""
    data = await image.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "image_too_large")
    try:
        result = street_check.check(io.BytesIO(data))
    except Exception:
        raise HTTPException(422, "not_an_image")
    return result.to_dict()


@app.get("/street-check/trafficcam")
def trafficcam_summary(night_only: bool = True, limit: int = 50):
    """Results of scripts/build_street_index.py on the TrafficCAM dataset."""
    if not STREET_INDEX.exists():
        raise HTTPException(404, "Run scripts/download_trafficcam.sh and scripts/build_street_index.py first")
    index = json.loads(STREET_INDEX.read_text())
    clips = [c for c in index["clips"] if c["night_by_time"] or not night_only]
    return {"summary": index["summary"], "clips": clips[:limit]}
