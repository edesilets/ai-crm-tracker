from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import cache
from .db import get_db
from .routers import trips, vehicles

app = FastAPI(
    title="Vehicle Tracking",
    description="Vehicles, trips to CRM job sites, and live GPS positions.",
)
app.include_router(vehicles.router)
app.include_router(trips.router)


@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    result, ok = {}, True
    try:
        db.execute(text("SELECT 1"))
        result["postgres"] = "ok"
    except Exception as exc:
        result["postgres"], ok = f"error: {exc}", False
    try:
        cache.client.ping()
        result["redis"] = "ok"
    except Exception as exc:
        result["redis"], ok = f"error: {exc}", False
    result["status"] = "ok" if ok else "error"
    return JSONResponse(result, status_code=200 if ok else 503)
