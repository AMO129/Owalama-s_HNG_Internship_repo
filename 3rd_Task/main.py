import asyncio
import httpx
import os
import uuid
import re
import time

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, asc, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# -----------------------------------------------
# DATABASE SETUP
# -----------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# -----------------------------------------------
# UUID v7 GENERATOR
# UUID v7 is time-ordered, which is better for database indexing
# -----------------------------------------------

def uuid7() -> str:
    # Get current time in milliseconds
    timestamp_ms = int(time.time() * 1000)

    # Pack the timestamp into the first 48 bits
    time_high = (timestamp_ms >> 16) & 0xFFFFFFFF
    time_low = timestamp_ms & 0xFFFF

    # Generate random bits for the rest
    rand_a = uuid.uuid4().int & 0x0FFF          # 12 random bits
    rand_b = uuid.uuid4().int & 0x3FFFFFFFFFFFFFFF  # 62 random bits

    # Combine everything into a UUID v7 format
    uuid_int = (time_high << 96) | (time_low << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b

    # Format as a proper UUID string
    hex_str = f"{uuid_int:032x}"
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"


# -----------------------------------------------
# DATABASE MODEL
# -----------------------------------------------

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, index=True)
    gender = Column(String)
    gender_probability = Column(Float)
    age = Column(Integer)
    age_group = Column(String)
    country_id = Column(String)
    country_name = Column(String)          # Required field added
    country_probability = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


# -----------------------------------------------
# APP SETUP
# -----------------------------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------

def get_age_group(age: int) -> str:
    if age <= 12:
        return "child"
    if age <= 19:
        return "teenager"
    if age <= 59:
        return "adult"
    return "senior"


def profile_to_dict(p: Profile) -> dict:
    # Reusable function to turn a Profile object into a clean dictionary
    return {
        "id": p.id,
        "name": p.name,
        "gender": p.gender,
        "gender_probability": p.gender_probability,
        "age": p.age,
        "age_group": p.age_group,
        "country_id": p.country_id,
        "country_name": p.country_name,
        "country_probability": p.country_probability,
        "created_at": p.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if p.created_at else None
    }


# -----------------------------------------------
# NATURAL LANGUAGE PARSER
# Converts plain English queries into filter dictionaries
# Rule-based only — no AI or LLMs used
# -----------------------------------------------

# Country name to ISO code mapping (West/East African focus based on dataset)
COUNTRY_MAP = {
    "nigeria": "NG", "ghana": "GH", "kenya": "KE", "angola": "AO",
    "senegal": "SN", "cameroon": "CM", "ethiopia": "ET", "tanzania": "TZ",
    "uganda": "UG", "ivory coast": "CI", "benin": "BJ", "togo": "TG",
    "mali": "ML", "niger": "NE", "burkina faso": "BF", "guinea": "GN",
    "mozambique": "MZ", "zambia": "ZM", "zimbabwe": "ZW", "somalia": "SO",
    "south africa": "ZA", "egypt": "EG", "morocco": "MA", "tunisia": "TN",
    "algeria": "DZ", "libya": "LY", "sudan": "SD", "chad": "TD",
    "rwanda": "RW", "burundi": "BI", "malawi": "MW", "namibia": "NA",
    "botswana": "BW", "lesotho": "LS", "swaziland": "SZ", "eswatini": "SZ",
    "gabon": "GA", "congo": "CG", "liberia": "LR", "sierra leone": "SL",
    "gambia": "GM", "mauritania": "MR", "cape verde": "CV",
    "united states": "US", "usa": "US", "uk": "GB", "united kingdom": "GB",
    "france": "FR", "germany": "DE", "canada": "CA", "australia": "AU",
    "brazil": "BR", "india": "IN", "china": "CN", "japan": "JP",
}


def parse_natural_language(q: str) -> dict | None:
    """
    Takes a plain English query string and returns a filters dictionary.
    Returns None if the query cannot be interpreted at all.

    Supported keywords:
    - Gender: "male", "males", "female", "females", "men", "women", "man", "woman"
    - Age descriptors: "young" (16-24), "old"/"elderly"/"senior" (60+), "adult" (20-59), "teen"/"teenager" (13-19), "child"/"children" (0-12)
    - Age numbers: "above 30", "over 25", "below 40", "under 18", "between 20 and 35"
    - Country: "from nigeria", "in kenya", country names mapped to ISO codes
    - Age group: "adult", "teenager", "child", "senior"
    """
    filters = {}
    text = q.lower().strip()

    # --- GENDER detection ---
    if re.search(r'\b(male|males|man|men)\b', text):
        filters["gender"] = "male"
    elif re.search(r'\b(female|females|woman|women)\b', text):
        filters["gender"] = "female"

    # --- AGE DESCRIPTOR detection ---
    if re.search(r'\byoung\b', text):
        filters["min_age"] = 16
        filters["max_age"] = 24

    elif re.search(r'\b(elderly|senior|old)\b', text):
        filters["min_age"] = 60

    elif re.search(r'\b(teen|teenager|teenagers|teens)\b', text):
        filters["age_group"] = "teenager"

    elif re.search(r'\b(child|children|kids|kid)\b', text):
        filters["age_group"] = "child"

    elif re.search(r'\badult\b', text) and "young" not in text:
        filters["age_group"] = "adult"

    # --- NUMERIC AGE RANGES ---
    # Pattern: "above 30" or "over 30"
    above_match = re.search(r'\b(above|over)\s+(\d+)\b', text)
    if above_match:
        filters["min_age"] = int(above_match.group(2))

    # Pattern: "below 40" or "under 40"
    below_match = re.search(r'\b(below|under)\s+(\d+)\b', text)
    if below_match:
        filters["max_age"] = int(below_match.group(2))

    # Pattern: "between 20 and 35"
    between_match = re.search(r'\bbetween\s+(\d+)\s+and\s+(\d+)\b', text)
    if between_match:
        filters["min_age"] = int(between_match.group(1))
        filters["max_age"] = int(between_match.group(2))

    # --- COUNTRY detection ---
    # First check two-letter ISO codes like "from NG"
    iso_match = re.search(r'\b(from|in)\s+([A-Z]{2})\b', q)  # use original case for ISO
    if iso_match:
        filters["country_id"] = iso_match.group(2).upper()
    else:
        # Try matching full country names
        for country_name, iso_code in COUNTRY_MAP.items():
            if country_name in text:
                filters["country_id"] = iso_code
                break

    # If we found nothing at all, return None to signal "can't interpret"
    if not filters:
        return None

    return filters


# -----------------------------------------------
# ENDPOINT 1: CREATE PROFILE (from your existing code, cleaned up)
# -----------------------------------------------

@app.post("/api/profiles", status_code=201)
async def create_profile(request: Request, response: Response):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid JSON"})

    name_raw = payload.get("name")
    if not name_raw or not isinstance(name_raw, str) or not name_raw.strip():
        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing or empty name"})

    name = name_raw.lower().strip()
    db = SessionLocal()

    try:
        # Check if profile already exists (idempotency)
        existing = db.query(Profile).filter(Profile.name == name).first()
        if existing:
            return {"status": "success", "message": "Profile already exists", "data": profile_to_dict(existing)}

        # Call the three external APIs at the same time
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                responses = await asyncio.gather(
                    client.get(f"https://api.genderize.io?name={name}"),
                    client.get(f"https://api.agify.io?name={name}"),
                    client.get(f"https://api.nationalize.io?name={name}")
                )
                g_data, a_data, n_data = [r.json() for r in responses]
            except Exception:
                return JSONResponse(status_code=502, content={"status": "error", "message": "Upstream service failure"})

        # Validate the API responses
        if not g_data.get("gender"):
            return JSONResponse(status_code=502, content={"status": "error", "message": "Genderize returned an invalid response"})
        if a_data.get("age") is None:
            return JSONResponse(status_code=502, content={"status": "error", "message": "Agify returned an invalid response"})
        if not n_data.get("country"):
            return JSONResponse(status_code=502, content={"status": "error", "message": "Nationalize returned an invalid response"})

        top_country = max(n_data["country"], key=lambda x: x["probability"])

        # Look up the country name from our map (reverse lookup by ISO code)
        iso_to_name = {v: k.title() for k, v in COUNTRY_MAP.items()}
        country_name = iso_to_name.get(top_country["country_id"], top_country["country_id"])

        new_profile = Profile(
            id=uuid7(),
            name=name,
            gender=g_data["gender"],
            gender_probability=g_data["probability"],
            age=a_data["age"],
            age_group=get_age_group(a_data["age"]),
            country_id=top_country["country_id"],
            country_name=country_name,
            country_probability=top_country["probability"]
        )

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        return {"status": "success", "data": profile_to_dict(new_profile)}

    finally:
        db.close()


# -----------------------------------------------
# ENDPOINT 2: GET ALL PROFILES with filtering, sorting, pagination
# -----------------------------------------------

@app.get("/api/profiles")
async def get_profiles(
    # Filters
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    country_id: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    min_gender_probability: Optional[float] = None,
    min_country_probability: Optional[float] = None,
    # Sorting
    sort_by: Optional[str] = Query(default=None, regex="^(age|created_at|gender_probability)$"),
    order: Optional[str] = Query(default="asc", regex="^(asc|desc)$"),
    # Pagination
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50)
):
    db = SessionLocal()
    query = db.query(Profile)

    # Apply all the filters if they were provided
    if gender:
        query = query.filter(Profile.gender.ilike(gender))
    if age_group:
        query = query.filter(Profile.age_group.ilike(age_group))
    if country_id:
        query = query.filter(Profile.country_id.ilike(country_id))
    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    if min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= min_gender_probability)
    if min_country_probability is not None:
        query = query.filter(Profile.country_probability >= min_country_probability)

    # Apply sorting
    if sort_by:
        sort_column = getattr(Profile, sort_by)
        query = query.order_by(desc(sort_column) if order == "desc" else asc(sort_column))

    # Count total BEFORE pagination (needed for the response)
    total = query.count()

    # Apply pagination
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()

    db.close()

    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "data": [profile_to_dict(p) for p in results]
    }


# -----------------------------------------------
# ENDPOINT 3: NATURAL LANGUAGE SEARCH
# -----------------------------------------------

@app.get("/api/profiles/search")
async def search_profiles(
    q: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50)
):
    # Make sure the query param was actually provided
    if not q or not q.strip():
        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing or empty parameter: q"})

    # Try to parse the natural language query into filters
    filters = parse_natural_language(q.strip())

    if filters is None:
        return JSONResponse(status_code=200, content={"status": "error", "message": "Unable to interpret query"})

    db = SessionLocal()
    query = db.query(Profile)

    # Apply whatever filters the parser found
    if "gender" in filters:
        query = query.filter(Profile.gender == filters["gender"])
    if "age_group" in filters:
        query = query.filter(Profile.age_group == filters["age_group"])
    if "country_id" in filters:
        query = query.filter(Profile.country_id == filters["country_id"])
    if "min_age" in filters:
        query = query.filter(Profile.age >= filters["min_age"])
    if "max_age" in filters:
        query = query.filter(Profile.age <= filters["max_age"])

    total = query.count()
    offset = (page - 1) * limit
    results = query.offset(offset).limit(limit).all()

    db.close()

    return {
        "status": "success",
        "page": page,
        "limit": limit,
        "total": total,
        "query_interpreted_as": filters,   # helpful for debugging what the parser understood
        "data": [profile_to_dict(p) for p in results]
    }


# -----------------------------------------------
# ENDPOINT 4: GET SINGLE PROFILE
# -----------------------------------------------

@app.get("/api/profiles/{profile_id}")
async def get_single(profile_id: str):
    db = SessionLocal()
    p = db.query(Profile).filter(Profile.id == profile_id).first()
    db.close()

    if not p:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Profile not found"})

    return {"status": "success", "data": profile_to_dict(p)}


# -----------------------------------------------
# ENDPOINT 5: DELETE PROFILE
# -----------------------------------------------

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    db = SessionLocal()
    p = db.query(Profile).filter(Profile.id == profile_id).first()

    if not p:
        db.close()
        return JSONResponse(status_code=404, content={"status": "error", "message": "Profile not found"})

    db.delete(p)
    db.commit()
    db.close()

    return Response(status_code=204)
