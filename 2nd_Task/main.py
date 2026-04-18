#LIBRARIES

import asyncio

import httpx

import os

import uuid

from datetime import datetime, timezone

from typing import Optional



from fastapi import FastAPI, Request, Response, status

from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import sessionmaker



#DATABASE SETUP

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

if DATABASE_URL.startswith("postgres://"):

    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)



engine = create_engine(

    DATABASE_URL,

    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()





#THE MODEL

class Profile(Base):

    __tablename__ = "profiles"

    id = Column(String, primary_key=True)

    name = Column(String, unique=True, index=True)

    gender = Column(String)

    gender_probability = Column(Float)

    sample_size = Column(Integer)

    age = Column(Integer)

    age_group = Column(String)

    country_id = Column(String)

    country_probability = Column(Float)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))





Base.metadata.create_all(bind=engine)



app = FastAPI()



#CORS (Required for Grading)

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_methods=["*"],

    allow_headers=["*"],

)





def get_age_group(age: int) -> str:

    if age <= 12: return "child"

    if age <= 19: return "teenager"

    if age <= 59: return "adult"

    return "senior"





#ENDPOINTS



@app.post("/api/profiles", status_code=201)

async def create_profile(request: Request, response: Response):

    # Parse body manually to ensure clean error handling

    try:

        payload = await request.json()

    except:

        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid JSON"})



    name_raw = payload.get("name")

    if not name_raw or not isinstance(name_raw, str):

        return JSONResponse(status_code=400, content={"status": "error", "message": "Missing or empty name"})



    name = name_raw.lower().strip()

    db = SessionLocal()



    try:

        # Idempotency

        existing = db.query(Profile).filter(Profile.name == name).first()

        if existing:

            return {

                "status": "success",

                "message": "Profile already exists",

                "data": {

                    "id": existing.id,

                    "name": existing.name,

                    "gender": existing.gender,

                    "gender_probability": existing.gender_probability,

                    "sample_size": existing.sample_size,

                    "age": existing.age,

                    "age_group": existing.age_group,

                    "country_id": existing.country_id,

                    "country_probability": existing.country_probability,

                    "created_at": existing.created_at.isoformat().replace("+00:00", "Z")

                }

            }



        #MULTI-API INTEGRATION

        async with httpx.AsyncClient(timeout=10.0) as client:

            try:

                res_list = await asyncio.gather(

                    client.get(f"https://api.genderize.io?name={name}"),

                    client.get(f"https://api.agify.io?name={name}"),

                    client.get(f"https://api.nationalize.io?name={name}")

                )

                g_data, a_data, n_data = [r.json() for r in res_list]

            except Exception:

                return JSONResponse(status_code=502, content={"status": "error", "message": "Upstream service failure"})



        # Strict 502 Validations

        if not g_data.get("gender"):

            return JSONResponse(status_code=502,

                                content={"status": "error", "message": "Genderize returned an invalid response"})

        if a_data.get("age") is None:

            return JSONResponse(status_code=502,

                                content={"status": "error", "message": "Agify returned an invalid response"})

        if not n_data.get("country"):

            return JSONResponse(status_code=502,

                                content={"status": "error", "message": "Nationalize returned an invalid response"})



        top_country = max(n_data["country"], key=lambda x: x["probability"])



        # Create Profile

        new_profile = Profile(

            id=str(uuid.uuid4()),

            name=name,

            gender=g_data["gender"],

            gender_probability=g_data["probability"],

            sample_size=g_data["count"],

            age=a_data["age"],

            age_group=get_age_group(a_data["age"]),

            country_id=top_country["country_id"],

            country_probability=top_country["probability"]

        )



        db.add(new_profile)

        db.commit()

        db.refresh(new_profile)



        return {

            "status": "success",

            "data": {

                "id": new_profile.id,

                "name": new_profile.name,

                "gender": new_profile.gender,

                "gender_probability": new_profile.gender_probability,

                "sample_size": new_profile.sample_size,

                "age": new_profile.age,

                "age_group": new_profile.age_group,

                "country_id": new_profile.country_id,

                "country_probability": new_profile.country_probability,

                "created_at": new_profile.created_at.isoformat().replace("+00:00", "Z")

            }

        }

    finally:

        db.close()





@app.get("/api/profiles")

async def get_profiles(gender: Optional[str] = None, country_id: Optional[str] = None, age_group: Optional[str] = None):

    db = SessionLocal()

    query = db.query(Profile)



    # Case-Insensitive Filtering

    if gender: query = query.filter(Profile.gender.ilike(gender))

    if country_id: query = query.filter(Profile.country_id.ilike(country_id))

    if age_group: query = query.filter(Profile.age_group.ilike(age_group))



    results = query.all()

    db.close()



    return {

        "status": "success",

        "count": len(results),

        "data": [

            {

                "id": p.id,

                "name": p.name,

                "gender": p.gender,

                "age": p.age,

                "age_group": p.age_group,

                "country_id": p.country_id

            } for p in results

        ]

    }





@app.get("/api/profiles/{profile_id}")

async def get_single(profile_id: str):

    db = SessionLocal()

    p = db.query(Profile).filter(Profile.id == profile_id).first()

    db.close()

    if not p:

        return JSONResponse(status_code=404, content={"status": "error", "message": "Profile not found"})

    return {

        "status": "success",

        "data": {

            "id": p.id,

            "name": p.name,

            "gender": p.gender,

            "gender_probability": p.gender_probability,

            "sample_size": p.sample_size,

            "age": p.age,

            "age_group": p.age_group,

            "country_id": p.country_id,

            "country_probability": p.country_probability,

            "created_at": p.created_at.isoformat().replace("+00:00", "Z")

        }

    }





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
