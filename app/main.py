# app/main.py (fragmento)
import os
from fastapi import FastAPI
from .seed import bootstrap_if_empty
from .db import Base, engine

API_PREFIX = os.getenv("API_PREFIX", "").rstrip("/")

def pref(path: str) -> str:
    return f"{API_PREFIX}{path}" if API_PREFIX else path

app = FastAPI(
    title="Psych CBR API",
    version="1.0.0",
    docs_url=pref("/docs"),
    redoc_url=pref("/redoc"),
    openapi_url=pref("/openapi.json"),
)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_ON_STARTUP", "false").lower() in ("1", "true", "yes"):
        bootstrap_if_empty()
