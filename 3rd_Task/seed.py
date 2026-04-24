"""
Seed Script — loads 2026 profiles from a JSON file into the database.
Run this once before starting the server:  python seed.py

Re-running it is safe — it skips profiles that already exist (no duplicates).
"""

import json
import os
import sys
import time
import uuid

from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the model and helpers from main.py
from main import Base, Profile, get_age_group, uuid7, COUNTRY_MAP


# -----------------------------------------------
# DATABASE CONNECTION
# -----------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -----------------------------------------------
# COUNTRY LOOKUP HELPER
# Reverse the COUNTRY_MAP to go from ISO code -> country name
# -----------------------------------------------

ISO_TO_NAME = {v: k.title() for k, v in COUNTRY_MAP.items()}

def get_country_name(iso_code: str) -> str:
    # Try to find the full name; fall back to the ISO code itself if not found
    return ISO_TO_NAME.get(iso_code.upper(), iso_code.upper())


# -----------------------------------------------
# MAIN SEED FUNCTION
# -----------------------------------------------

def seed(json_file_path: str):
    # Make sure the file actually exists
    if not os.path.exists(json_file_path):
        print(f"ERROR: File not found: {json_file_path}")
        sys.exit(1)

    # Load the JSON data
    with open(json_file_path, "r", encoding="utf-8") as f:
        profiles_data = json.load(f)

    print(f"Loaded {len(profiles_data)} profiles from {json_file_path}")

    db = SessionLocal()

    inserted = 0
    skipped = 0

    for item in profiles_data:
        # Grab the name and clean it up
        name = str(item.get("name", "")).lower().strip()

        if not name:
            skipped += 1
            continue

        # Skip if this name already exists in the database
        existing = db.query(Profile).filter(Profile.name == name).first()
        if existing:
            skipped += 1
            continue

        # Pull the values from the JSON, with safe fallbacks
        gender = item.get("gender", "unknown")
        gender_probability = float(item.get("gender_probability", 0.0))
        age = int(item.get("age", 0))
        country_id = str(item.get("country_id", "")).upper()
        country_probability = float(item.get("country_probability", 0.0))

        # Get the full country name
        country_name = item.get("country_name") or get_country_name(country_id)

        # Build the profile object
        profile = Profile(
            id=uuid7(),
            name=name,
            gender=gender,
            gender_probability=gender_probability,
            age=age,
            age_group=get_age_group(age),
            country_id=country_id,
            country_name=country_name,
            country_probability=country_probability,
            created_at=datetime.now(timezone.utc)
        )

        db.add(profile)
        inserted += 1

        # Commit in batches of 100 so we don't hold one huge transaction
        if inserted % 100 == 0:
            db.commit()
            print(f"  {inserted} profiles inserted so far...")

    # Final commit for any remaining records
    db.commit()
    db.close()

    print(f"\nDone! Inserted: {inserted} | Skipped (already existed): {skipped}")


# -----------------------------------------------
# ENTRY POINT
# -----------------------------------------------

if __name__ == "__main__":
    # Default path — change this to wherever your JSON file is
    json_path = sys.argv[1] if len(sys.argv) > 1 else "profiles.json"
    seed(json_path)
