import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def initialize_database():
    # 1. Load the database URL from the .env file
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("Error: DATABASE_URL not found in your .env file.")
        return

    # Fix: SQLAlchemy 1.4+ requires the dialect to be "postgresql://"
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print("Connecting to Neon database...")
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
    )

    csv_to_tables = {
        "world_cup_players.csv": "players",
        "world_cup_countries.csv": "countries",
        "world_cup_locations.csv": "locations",
        "world_cup_matches.csv": "matches"
    }

    # Using engine.begin() ensures all our raw SQL commands are committed automatically
    with engine.begin() as conn:
        
        # ---------------------------------------------------------
        # PHASE 0: The Clean Slate (CRITICAL FIX)
        # ---------------------------------------------------------
        print("--- PHASE 0: Wiping Old Schema ---")
        # CASCADE completely safely deletes the tables AND their existing foreign key rules
        conn.execute(text("DROP TABLE IF EXISTS players, matches, countries, locations CASCADE;"))
        print(" ✓ Old tables and foreign keys successfully dropped.")

        # ---------------------------------------------------------
        # PHASE 1: Import all Data
        # ---------------------------------------------------------
        print("\n--- PHASE 1: Importing Data ---")
        for file_name, table_name in csv_to_tables.items():
            print(f"Reading '{file_name}'...")
            try:
                df = pd.read_csv(file_name)
                if table_name == "matches" and "Actual_Winner" not in df.columns:
                    df["Actual_Winner"] = None
                if table_name == "matches" and "Predicted_Winner" not in df.columns:
                    df["Predicted_Winner"] = None
                # Write the dataframe to SQL
                df.to_sql(table_name, con=conn, if_exists='replace', index=False)
                print(f" ✓ Successfully imported {len(df)} rows into '{table_name}'.")
            except FileNotFoundError:
                print(f" x Error: Could not find {file_name}.")
                return

        # ---------------------------------------------------------
        # PHASE 2: Assign Primary Keys
        # ---------------------------------------------------------
        print("\n--- PHASE 2: Setting Primary Keys ---")
        try:
            conn.execute(text('ALTER TABLE locations ADD PRIMARY KEY ("Location_Name");'))
            print(" ✓ Set PK on locations (Location_Name)")
            
            conn.execute(text('ALTER TABLE countries ADD PRIMARY KEY ("Name");'))
            print(" ✓ Set PK on countries (Name)")
            
            conn.execute(text('ALTER TABLE matches ADD PRIMARY KEY ("Match_ID");'))
            print(" ✓ Set PK on matches (Match_ID)")
            
            conn.execute(text('ALTER TABLE players ADD COLUMN "Player_ID" SERIAL PRIMARY KEY;'))
            print(" ✓ Created and set Surrogate PK on players (Player_ID)")
            
        except Exception as e:
            print(f" x Error setting primary keys: {e}")
            return

        # ---------------------------------------------------------
        # PHASE 3: Assign Foreign Keys
        # ---------------------------------------------------------
        print("\n--- PHASE 3: Setting Foreign Keys ---")
        try:
            conn.execute(text('''
                ALTER TABLE countries 
                ADD CONSTRAINT fk_base_camp 
                FOREIGN KEY ("Base_Camp_City") REFERENCES locations("Location_Name");
            '''))
            print(" ✓ Linked Countries -> Locations (Base Camp)")

            conn.execute(text('''
                ALTER TABLE players 
                ADD CONSTRAINT fk_player_country 
                FOREIGN KEY ("Country") REFERENCES countries("Name");
            '''))
            print(" ✓ Linked Players -> Countries")

            conn.execute(text('''
                ALTER TABLE matches 
                ADD CONSTRAINT fk_match_stadium 
                FOREIGN KEY ("Stadium_Name") REFERENCES locations("Location_Name");
            '''))
            print(" ✓ Linked Matches -> Locations (Stadium)")

            conn.execute(text('''
                ALTER TABLE matches 
                ADD CONSTRAINT fk_match_team_a 
                FOREIGN KEY ("Team_A") REFERENCES countries("Name") NOT VALID;
            '''))
            
            conn.execute(text('''
                ALTER TABLE matches 
                ADD CONSTRAINT fk_match_team_b 
                FOREIGN KEY ("Team_B") REFERENCES countries("Name") NOT VALID;
            '''))
            print(" ✓ Linked Matches -> Countries (Team A and Team B)")

        except Exception as e:
            print(f"\n x Foreign Key Error: {e}")

    print("\nDatabase architecture complete! You are ready to start the simulation.")

if __name__ == "__main__":
    initialize_database()
