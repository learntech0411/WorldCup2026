from pathlib import Path
import sys

from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.utilities import calculate_total_utility_values, calculate_base_strengths, calculate_match_power_score
from app.predictions import run_predictions_for_matches

load_dotenv(BACKEND_DIR / ".env")
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

calculate_total_utility_values(engine, stage="group")
calculate_base_strengths(engine)
run_predictions_for_matches(engine, 1, 72)

