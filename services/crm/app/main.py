from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db
from .routers import customers, quotes

app = FastAPI(title="CRM", description="Customers, contact info and quotes.")
app.include_router(customers.router)
app.include_router(quotes.router)


@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse({"status": "error", "postgres": str(exc)}, status_code=503)
    return {"status": "ok"}
