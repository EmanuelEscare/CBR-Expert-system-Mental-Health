import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from .db import engine, Base
from .api import router
from .seed import bootstrap_if_empty
import os

load_dotenv()


app = FastAPI(title="Psych CBR API", version="1.0.0")


origins = os.getenv("ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
CORSMiddleware,
allow_origins=origins,
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    if os.getenv("BOOTSTRAP", "0") not in ("0","false","False"):
        bootstrap_if_empty()


app.include_router(router, prefix="/api/psych-cbr")