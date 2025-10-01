from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os


DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://psych_user:strongpass@127.0.0.1:3306/psych_cbr")


engine = create_engine(
DATABASE_URL,
pool_pre_ping=True,
pool_recycle=3600,
)


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass