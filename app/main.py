# app/main.py (fragmento)
import os
from fastapi import FastAPI
from .seed import bootstrap_if_empty
from .db import Base, engine

app = FastAPI(title="Psych CBR API", version="1.0.0")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_ON_STARTUP", "false").lower() in ("1", "true", "yes"):
        bootstrap_if_empty()
