# Name Classifier API
# A backend service that accepts a name, fetches demographic data from multiple external APIs (Genderize, Agify, and Nationalize), classifies the data, and stores it in a persistent database.

# Features
# Data Orchestration: Calls three external APIs in parallel for optimal performance.ss

# Intelligent Classification: Categorizes users into age groups (child, teenager, adult, senior).

# Idempotency: Prevents duplicate records for the same name.

# Persistent Storage: Uses SQLAlchemy to support SQLite (local) and PostgreSQL (production/Railway).

# Filtering: Advanced GET endpoints with case-insensitive filtering by gender, age group, or country.

# Tech Stack
# Language: Python 3.10+
# Framework: FastAPI

# Database: SQLAlchemy (SQLite/PostgreSQL)

# HTTP Client: HTTPX (Asynchronous)

# Requirements
# cTo run this locally, you need the following dependencies. You should save these in a file named requirements.txt:

# Plaintext
# fastapi
# uvicorn
# httpx
# sqlalchemy
# psycopg2-binary


# Railway Deployed
# API Endpoints
# Create Profile
# POST /api/profiles

# JSON
# { "name": "ella" }
# Get All Profiles (with optional filters)
# GET /api/profiles?gender=female&age_group=adult

# Get Single Profile
# GET /api/profiles/{uuid}

# Delete Profile
# DELETE /api/profiles/{uuid}

# Error Handling
# The API strictly follows the requested error formats:

# 400: Missing/Empty name.

# 404: Profile ID not found.

# 502: Upstream service (External API) returned an invalid response or is down.

# 422: Invalid JSON payload.

# Grading Compliance
# CORS: Enabled for all origins (*) to allow grading scripts.

# UUID: Generates unique IDs for every record.

# Timestamps: All dates are stored and served in UTC ISO 8601 format.