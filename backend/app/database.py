from functools import lru_cache
from pathlib import Path
from typing import Generator
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def get_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found in backend/.env")
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return db_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_database_url())


def get_connection() -> Generator[Connection, None, None]:
    with get_engine().connect() as connection:
        yield connection
