import os
from datetime import date as date_cls, datetime
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DailyEntryPayload(BaseModel):
    warmup: Dict[str, bool] = {}
    food: Dict[str, bool] = {}
    notes: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------------- Daily Tracker API ----------------

COLLECTION = db["dailyentry"]


def normalize_date(d: Optional[str]) -> str:
    if d:
        return d
    return date_cls.today().strftime("%Y-%m-%d")


@app.get("/tracker/{entry_date}")
def get_entry(entry_date: str):
    doc = COLLECTION.find_one({"date": entry_date}, {"_id": 0})
    if not doc:
        # Return empty structure if not found
        return {"date": entry_date, "warmup": {}, "food": {}, "notes": None}
    return doc


@app.put("/tracker/{entry_date}")
def upsert_entry(entry_date: str, payload: DailyEntryPayload):
    now = datetime.utcnow()
    update_doc = {
        "$set": {
            "date": entry_date,
            "warmup": payload.warmup or {},
            "food": payload.food or {},
            "notes": payload.notes,
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    COLLECTION.update_one({"date": entry_date}, update_doc, upsert=True)
    doc = COLLECTION.find_one({"date": entry_date}, {"_id": 0})
    return doc


@app.get("/tracker")
def month_summary(month: str = Query(..., description="YYYY-MM")):
    prefix = month + "-"
    cursor = COLLECTION.find({"date": {"$regex": f"^{prefix}"}}, {"_id": 0, "date": 1, "warmup": 1, "food": 1})
    results: List[Dict[str, Any]] = []
    for d in cursor:
        warmup_done = sum(1 for v in (d.get("warmup") or {}).values() if v)
        food_done = sum(1 for v in (d.get("food") or {}).values() if v)
        results.append({
            "date": d["date"],
            "warmup_count": warmup_done,
            "food_count": food_done,
        })
    return {"month": month, "days": results}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
