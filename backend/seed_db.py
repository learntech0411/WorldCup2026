import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Load the variables from the .env file into Python's environment
load_dotenv()

# 2. Safely grab the database URL
# This looks for "DATABASE_URL" in the .env file and assigns it to the variable
DATABASE_URL = os.getenv("DATABASE_URL")

# Make sure it actually loaded!
if not DATABASE_URL:
    raise ValueError("No DATABASE_URL found. Check your .env file.")

# 3. Create the connection engine using the safe variable
engine = create_engine(DATABASE_URL)