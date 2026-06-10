# World Cup 2026 Predictor

This project predicts World Cup 2026 match results and visualizes the tournament flow in a React app. It combines scraped country, player, location, and match data with a backend prediction model, then displays probabilities, predicted scores, and knockout progression in the frontend.

## How It Works

The project starts by collecting several types of data that can influence a football match. For each country, the backend uses an Elo rating, group assignment, base camp location, and squad data. For each player, it uses transfer value, position, age, club, and injury status. For the tournament itself, it stores all 104 matches, the teams involved, match dates, and stadium locations. Stadiums and base camps are geocoded with GeoPy so the model can calculate distances and timezones.

Player market value is the starting point for squad strength, but it is transformed before being used. The backend applies multipliers for age, position, rank within the national team, and club synergy. Experienced players can receive a small boost, different positions are weighted differently, the most important players in a squad keep more weight, and players from the same club can receive a small chemistry bonus. If a player is injured, their utility is set to zero.

After all player utility values are calculated, they are summed for each country and blended with that country's Elo rating. This creates a base team strength that combines historical national-team performance with current squad quality.

For every match, the model converts base strength into a match power score. It adds a home boost for Mexico, the United States, and Canada when they play in their own country. It adjusts for rest days by rewarding the better-rested team and penalizing the team with fewer days between matches. It also estimates travel with the Haversine distance formula: in the group stage, travel is measured from the team base camp to the stadium; in the knockout stage, it can use the previous knockout stadium if the team has already played one. Distance and timezone changes become small Elo-style penalties.

The two match power scores are then converted into expected goals. Those expected goals feed a Poisson model that estimates the probability of scorelines such as `0-0`, `1-0`, or `2-1`. A Dixon-Coles adjustment is applied to better handle common low-scoring football results, especially `0-0`, `1-0`, `0-1`, and `1-1`. From the final scoreline matrix, the backend selects the most likely exact score and sums the matrix into Team A win, Team B win, and draw probabilities.

The tournament prediction runs in stages. First, all group matches are predicted and group tables are built using points, goal difference, goals scored, Elo, and team name as tie-breakers. Then the Round of 32 is filled from the group rankings, including the best third-place teams. After that, each knockout round is predicted one round at a time, with winners advancing until the final.

## Tech Stack

- Frontend: React with Vite.
- Styling: CSS modules and custom component CSS. The app design was iterated with the Gemini frontend design skill for layout and visual polish.
- Backend: FastAPI, SQLAlchemy, pandas, and scraper utilities.
- Database: PostgreSQL hosted on the free Neon.tech tier.

## Setup

You need your own PostgreSQL database. The project was developed with a private Neon.tech database, so the included configuration will not work for other users unless they create their own database and set `DATABASE_URL`.

1. Clone the repository.

2. Create a Neon.tech PostgreSQL database, or use another PostgreSQL database.

3. Create `backend/.env` with your database URL:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB_NAME?sslmode=require
```

4. Install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5. Install frontend dependencies:

```bash
cd ../frontend
npm install
```

## Initialize The Database

Before running the backend API, create the database tables and load the initial CSV data:

```bash
cd backend
source .venv/bin/activate
python init_db.py
```

This reads the CSV files in `backend`, writes the `players`, `countries`, `locations`, and `matches` tables, and adds primary and foreign keys. You must run this against your own database URL in `backend/.env`.

## Run The Backend

From the `backend` folder:

```bash
source .venv/bin/activate
fastapi dev app/main.py
```

The API should be available at `http://localhost:8000`.

## Run The Frontend

From the `frontend` folder:

```bash
npm run dev
```

The frontend defaults to `http://localhost:8000/api` for backend data. To use a different backend URL, create `frontend/.env`:

```bash
VITE_API_PREFIX=http://localhost:8000/api
```

Then open the Vite URL shown in the terminal, usually `http://localhost:5173`.
