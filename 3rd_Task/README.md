# Zenith Profiles API

A FastAPI backend for managing and querying name-based demographic profiles using OOP-style inheritance and natural language search.

---

## Getting Started

### Install dependencies
```bash
pip install fastapi uvicorn sqlalchemy httpx
```

### Seed the database
Put your `profiles.json` file in the project folder, then run:
```bash
python seed.py profiles.json
```
Re-running this is safe — it skips any profiles that already exist.

### Start the server
```bash
uvicorn main:app --reload
```

---

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/profiles` | Create a profile by name (calls external APIs) |
| GET | `/api/profiles` | Get all profiles with filters, sorting, pagination |
| GET | `/api/profiles/search` | Natural language search |
| GET | `/api/profiles/{id}` | Get a single profile by ID |
| DELETE | `/api/profiles/{id}` | Delete a profile |

---

## GET /api/profiles — Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `gender` | string | `male` or `female` |
| `age_group` | string | `child`, `teenager`, `adult`, `senior` |
| `country_id` | string | ISO 2-letter code e.g. `NG` |
| `min_age` | int | Minimum age (inclusive) |
| `max_age` | int | Maximum age (inclusive) |
| `min_gender_probability` | float | e.g. `0.9` |
| `min_country_probability` | float | e.g. `0.7` |
| `sort_by` | string | `age`, `created_at`, `gender_probability` |
| `order` | string | `asc` or `desc` (default: `asc`) |
| `page` | int | Page number (default: 1) |
| `limit` | int | Results per page (default: 10, max: 50) |

**Example:**
```
GET /api/profiles?gender=male&country_id=NG&min_age=25&sort_by=age&order=desc&page=1&limit=10
```

---

## Natural Language Parsing — How It Works

`GET /api/profiles/search?q=young males from nigeria`

The parser is **entirely rule-based** — no AI or LLMs are involved. It scans the query string for recognizable keywords and patterns using regular expressions, then converts them into database filters.

### Keyword Mappings

#### Gender
| Query contains | Maps to |
|----------------|---------|
| `male`, `males`, `man`, `men` | `gender = male` |
| `female`, `females`, `woman`, `women` | `gender = female` |

#### Age Descriptors
| Query contains | Maps to |
|----------------|---------|
| `young` | `min_age = 16`, `max_age = 24` |
| `elderly`, `senior`, `old` | `min_age = 60` |
| `teen`, `teenager` | `age_group = teenager` |
| `child`, `children`, `kid` | `age_group = child` |
| `adult` | `age_group = adult` |

#### Numeric Age Patterns
| Query pattern | Maps to |
|---------------|---------|
| `above 30` / `over 30` | `min_age = 30` |
| `below 40` / `under 40` | `max_age = 40` |
| `between 20 and 35` | `min_age = 20`, `max_age = 35` |

#### Country
| Query pattern | Maps to |
|---------------|---------|
| `from nigeria` | `country_id = NG` |
| `in kenya` | `country_id = KE` |
| `from NG` | `country_id = NG` |

Supported country names include most African nations plus common global ones (US, UK, France, etc.). See `COUNTRY_MAP` in `main.py` for the full list.

### How Multiple Filters Work
All matched filters are combined with AND logic. So `young males from nigeria` maps to:
```
gender=male + min_age=16 + max_age=24 + country_id=NG
```

### Unrecognized Queries
If the parser finds no recognizable keywords at all, it returns:
```json
{ "status": "error", "message": "Unable to interpret query" }
```

---

## Limitations & Known Edge Cases

1. **"young" is not an age group** — It maps to ages 16–24 for parsing only. It is not stored in the database.

2. **No synonym expansion** — Words like "guys", "boys", "ladies", "girls" are not recognized. Only the keywords listed above are supported.

3. **Country name collisions** — "Congo" maps to CG (Republic of Congo). "Democratic Republic of Congo" is not handled separately.

4. **No negation support** — Queries like "not from Nigeria" or "excluding males" are not supported.

5. **No compound gender queries** — "male and female" does not filter by both genders simultaneously (SQL doesn't support `gender = male AND gender = female`). It will return whichever gender was detected last in the string.

6. **Age conflicts** — If both a descriptor (`young`) and a numeric pattern (`above 30`) appear, they will both apply and may produce contradictory filters (e.g. `min_age=16, max_age=24, min_age=30`). The numeric pattern will overwrite the descriptor's value.

7. **No fuzzy matching** — Typos like "nigerja" or "femal" won't be recognized.

8. **No probability filters in natural language** — Queries like "highly probable males" are not supported. Use the `/api/profiles` endpoint with `min_gender_probability` for this.

---

## Database Schema

| Field | Type | Notes |
|-------|------|-------|
| id | UUID v7 | Primary key, time-ordered |
| name | VARCHAR UNIQUE | Lowercase |
| gender | VARCHAR | `male` or `female` |
| gender_probability | FLOAT | 0.0 – 1.0 |
| age | INT | Exact age |
| age_group | VARCHAR | `child`, `teenager`, `adult`, `senior` |
| country_id | VARCHAR(2) | ISO code |
| country_name | VARCHAR | Full country name |
| country_probability | FLOAT | 0.0 – 1.0 |
| created_at | TIMESTAMP | UTC, auto-generated |
