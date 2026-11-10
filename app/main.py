import os

import psycopg
import redis
from fastapi import FastAPI

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ["REDIS_URL"]

app = FastAPI()
cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


@app.get("/")
def root():
    return {"message": "Hello from the Python app"}


@app.get("/health")
def health():
    status = {}
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"error: {exc}"
    try:
        cache.ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {exc}"
    return status


@app.get("/hits")
def hits():
    return {"hits": cache.incr("hits")}
