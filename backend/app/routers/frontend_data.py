import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Security
from math import asin, cos, radians, sin, sqrt
import os
from fastapi.security import APIKeyHeader
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from app.database import get_engine
from app.predictions import (
    _dixon_coles_matrix,
    _expected_goals,
    run_predictions_for_matches,
    winner_prediction,
)
from app.utilities import (
    HOME_COUNTRY_STADIUMS,
    calculate_all_group_score_matrices,
    calculate_match_power_score,
)


router = APIRouter(prefix="/api", tags=["frontend-data"])
EARTH_RADIUS_KM = 6371.0
COUNTRY_NAME_ALIASES = {
    "Curaçao": "Curacao",
    "Czech Republic": "Czechia",
}

# 1. Define the custom security header
API_KEY_NAME = "X-Keep-Alive-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# 2. Pull your secret token from Render's Environment Variables
SECRET_TOKEN = os.getenv("KEEP_ALIVE_TOKEN", "fallback_secret_for_local_testing")

def verify_token(api_key: str = Security(api_key_header)):
    if api_key != SECRET_TOKEN:
        # This will reveal exactly what cron-job sent vs what Render has loaded
        debug_message = f"Mismatch! cron-job sent: '{api_key}' | Render loaded: '{SECRET_TOKEN}'"
        print(debug_message) 
        raise HTTPException(status_code=403, detail=debug_message)
    return api_key

# 3. Protect the endpoint by injecting the dependency
@router.get("/health", dependencies=[Depends(verify_token)])
def keep_alive():
    return {"status": "awake"}


@router.get("/predicted-score/{match_id}")
def get_predicted_score(match_id: int, engine: Engine = Depends(get_engine)):
    match = _get_match(engine, match_id)
    prediction_columns = [
        "Predicted_Goals_A",
        "Predicted_Goals_B",
        "Winning_Probability_A",
        "Winning_Probability_B",
        "Draw_Probability",
    ]

    if any(_is_missing(match[column]) for column in prediction_columns):
        # Prevent crashing by checking if teams are resolved (countries don't contain digits)
        team_a, team_b = str(match["Team_A"]), str(match["Team_B"])
        if any(char.isdigit() for char in team_a) or any(char.isdigit() for char in team_b):
            return _sanitize({
                "Match_ID": match_id,
                "Predicted_Goals_A": None,
                "Predicted_Goals_B": None,
                "Winning_Probability_A": None,
                "Winning_Probability_B": None,
                "Draw_Probability": None,
            })

        power_score = calculate_match_power_score(engine, match_id)
        winner_prediction(
            engine,
            match_id,
            power_score["Match_Power_Score_A"],
            power_score["Match_Power_Score_B"],
        )
        match = _get_match(engine, match_id)

    return _sanitize(
        {
            "Match_ID": match_id,
            "Predicted_Goals_A": match["Predicted_Goals_A"],
            "Predicted_Goals_B": match["Predicted_Goals_B"],
            "Winning_Probability_A": match["Winning_Probability_A"],
            "Winning_Probability_B": match["Winning_Probability_B"],
            "Draw_Probability": match["Draw_Probability"],
        }
    )


@router.get("/current-score/{match_id}")
def get_current_score(match_id: int, engine: Engine = Depends(get_engine)):
    match = _get_match(engine, match_id)
    return _sanitize(
        {
            "Match_ID": match_id,
            "Goals_A": match["Goals_A"],
            "Goals_B": match["Goals_B"],
        }
    )


@router.get("/match-data")
def get_match_data(team_1: str, team_2: str, engine: Engine = Depends(get_engine)):
    if set(_country_name_variants(team_1)) & set(_country_name_variants(team_2)):
        raise HTTPException(status_code=400, detail="team_1 and team_2 must be different countries")

    with engine.connect() as connection:
        match = _get_played_match_between(connection, team_1, team_2)
        if match is None:
            raise HTTPException(
                status_code=404,
                detail=f"No played match found between {team_1} and {team_2}",
            )

        country_rows = {
            team_name: _get_country(connection, team_name)
            for team_name in (str(match["Team_A"]), str(match["Team_B"]))
        }
        power_score = calculate_match_power_score(connection, int(match["Match_ID"]))
        requested_teams = [
            _match_team_name(match, team_1),
            _match_team_name(match, team_2),
        ]
        team_payload = [
            _match_team_data(connection, match, power_score, country_rows, team_name)
            for team_name in requested_teams
        ]

    return _sanitize(
        {
            "Match_ID": int(match["Match_ID"]),
            "Team_A": match["Team_A"],
            "Team_B": match["Team_B"],
            "Teams": team_payload,
        }
    )


@router.get("/score-distribution")
def get_score_distribution(match_score_a: float, match_score_b: float):
    xg_a, xg_b = _expected_goals(match_score_a, match_score_b)
    matrix = _dixon_coles_matrix(xg_a, xg_b)
    matrix_rows = [
        {
            "Goals_A": int(goals_a),
            "Goals_B": int(goals_b),
            "Probability": float(probability),
        }
        for (goals_a, goals_b), probability in sorted(matrix.items())
    ]

    return _sanitize(
        {
            "Match_Score_A": float(match_score_a),
            "Match_Score_B": float(match_score_b),
            "Expected_Goals_A": float(xg_a),
            "Expected_Goals_B": float(xg_b),
            "Matrix": matrix_rows,
        }
    )


@router.get("/all-predicted-scores")
def get_all_predicted_scores(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        matches = connection.execute(
            text(
                '''
                SELECT
                    "Match_ID",
                    "Team_A",
                    "Team_B",
                    "Predicted_Goals_A",
                    "Predicted_Goals_B",
                    "Winning_Probability_A",
                    "Winning_Probability_B",
                    "Draw_Probability"
                FROM matches
                ORDER BY "Match_ID"
                '''
            )
        ).mappings().all()
    return _sanitize([dict(match) for match in matches])


@router.get("/all-current-scores")
def get_all_current_scores(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        matches = connection.execute(
            text(
                '''
                SELECT
                    "Match_ID",
                    "Team_A",
                    "Team_B",
                    "Goals_A",
                    "Goals_B"
                FROM matches
                ORDER BY "Match_ID"
                '''
            )
        ).mappings().all()
    return _sanitize([dict(match) for match in matches])


@router.get("/correct-outcome-predictions")
def get_correct_outcome_predictions(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        correct_predictions = connection.execute(
            text(
                '''
                SELECT COUNT(*)
                FROM matches
                WHERE "Goals_A" IS NOT NULL
                  AND "Goals_B" IS NOT NULL
                  AND (
                      ("Predicted_Goals_A" > "Predicted_Goals_B" AND "Goals_A" > "Goals_B")
                      OR ("Predicted_Goals_A" < "Predicted_Goals_B" AND "Goals_A" < "Goals_B")
                      OR ("Predicted_Goals_A" = "Predicted_Goals_B" AND "Goals_A" = "Goals_B")
                  )
                '''
            )
        ).scalar_one()
    return {"Correct_Outcome_Predictions": int(correct_predictions)}


@router.get("/played-matches-count")
def get_played_matches_count(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        played_matches = connection.execute(
            text(
                '''
                SELECT COUNT(*)
                FROM matches
                WHERE "Goals_A" IS NOT NULL
                  AND "Goals_B" IS NOT NULL
                '''
            )
        ).scalar_one()
    return {"Played_Matches": int(played_matches)}


@router.get("/correct-goal-difference-predictions")
def get_correct_goal_difference_predictions(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        correct_predictions = connection.execute(
            text(
                '''
                SELECT COUNT(*)
                FROM matches
                WHERE "Goals_A" IS NOT NULL
                  AND "Goals_B" IS NOT NULL
                  AND ("Predicted_Goals_A" - "Predicted_Goals_B") = ("Goals_A" - "Goals_B")
                '''
            )
        ).scalar_one()
    return {"Correct_Goal_Difference_Predictions": int(correct_predictions)}


@router.get("/correct-score-predictions")
def get_correct_score_predictions(engine: Engine = Depends(get_engine)):
    with engine.connect() as connection:
        correct_predictions = connection.execute(
            text(
                '''
                SELECT COUNT(*)
                FROM matches
                WHERE "Goals_A" IS NOT NULL
                  AND "Goals_B" IS NOT NULL
                  AND "Predicted_Goals_A" = "Goals_A"
                  AND "Predicted_Goals_B" = "Goals_B"
                '''
            )
        ).scalar_one()
    return {"Correct_Score_Predictions": int(correct_predictions)}


@router.get("/predicted-matrix/{group}")
def get_predicted_matrix(group: str, engine: Engine = Depends(get_engine)):
    _ensure_group_predictions_available(engine)
    matrices = calculate_all_group_score_matrices(engine, "Prediction")
    group_key = group.upper()
    if group_key not in matrices:
        raise HTTPException(status_code=404, detail=f"Group {group_key} not found")
    return {"Group": group_key, "Matrix": _dataframe_records(matrices[group_key])}


@router.get("/current-matrix/{group}")
def get_current_matrix(group: str, engine: Engine = Depends(get_engine)):
    matrices = calculate_all_group_score_matrices(engine, "Current")
    group_key = group.upper()
    if group_key not in matrices:
        raise HTTPException(status_code=404, detail=f"Group {group_key} not found")
    return {"Group": group_key, "Matrix": _dataframe_records(matrices[group_key])}


@router.get("/all-groups-predicted-matrix")
def get_all_groups_predicted_matrix(engine: Engine = Depends(get_engine)):
    _ensure_group_predictions_available(engine)
    matrices = calculate_all_group_score_matrices(engine, "Prediction")
    return {
        "Groups": {
            group: _dataframe_records(matrix)
            for group, matrix in matrices.items()
        }
    }


@router.get("/all-groups-current-matrix")
def get_all_groups_current_matrix(engine: Engine = Depends(get_engine)):
    matrices = calculate_all_group_score_matrices(engine, "Current")
    return {
        "Groups": {
            group: _dataframe_records(matrix)
            for group, matrix in matrices.items()
        }
    }


def _get_played_match_between(connection: Connection, team_1: str, team_2: str) -> dict | None:
    team_1_variants = _country_name_variants(team_1)
    team_2_variants = _country_name_variants(team_2)
    match = connection.execute(
        text(
            '''
            SELECT *
            FROM matches
            WHERE 
                ("Team_A" IN :team_1_variants AND "Team_B" IN :team_2_variants)
                OR ("Team_A" IN :team_2_variants AND "Team_B" IN :team_1_variants)
            ORDER BY "Match_ID" DESC
            LIMIT 1
            '''
        ).bindparams(
            bindparam("team_1_variants", expanding=True),
            bindparam("team_2_variants", expanding=True),
        ),
        {
            "team_1_variants": tuple(team_1_variants),
            "team_2_variants": tuple(team_2_variants),
        },
    ).mappings().first()
    return dict(match) if match is not None else None


def _match_team_name(match: dict, requested_team: str) -> str:
    requested_variants = set(_country_name_variants(requested_team))
    for match_team in (str(match["Team_A"]), str(match["Team_B"])):
        if requested_variants & set(_country_name_variants(match_team)):
            return match_team
    raise HTTPException(
        status_code=400,
        detail=f"{requested_team} did not play in match {match['Match_ID']}",
    )


def _country_name_variants(country_name: str) -> list[str]:
    country_name = str(country_name).strip()
    variants = {country_name}

    alias = COUNTRY_NAME_ALIASES.get(country_name)
    if alias:
        variants.add(alias)

    reverse_aliases = {
        display_name
        for display_name, canonical_name in COUNTRY_NAME_ALIASES.items()
        if canonical_name == country_name
    }
    variants.update(reverse_aliases)

    return sorted(variants)


def _match_team_data(
    connection: Connection,
    match: dict,
    power_score: dict,
    country_rows: dict[str, dict],
    team_name: str,
) -> dict:
    side = _team_side(match, team_name)
    country = country_rows.get(team_name)
    if country is None:
        raise HTTPException(status_code=404, detail=f"Country {team_name} not found")

    return {
        "Team": team_name,
        "Winning_Probability": match[f"Winning_Probability_{side}"],
        "Match_Score": power_score[f"Match_Power_Score_{side}"],
        "Total_Transfer_Market_Value": _total_transfer_market_value(connection, team_name),
        "Home_Advantage": _has_home_advantage(team_name, str(match["Stadium_Name"])),
        "Club_Synergies": country.get("Synergies", ""),
        "Injured_Players": country.get("Injured_Players", ""),
        "Days_Rested": _days_rested(connection, match, team_name),
        "Travel_Distance_KM": _base_camp_travel_distance_km(connection, match, country),
    }


def _team_side(match: dict, team_name: str) -> str:
    if team_name == str(match["Team_A"]):
        return "A"
    if team_name == str(match["Team_B"]):
        return "B"
    raise HTTPException(
        status_code=400,
        detail=f"{team_name} did not play in match {match['Match_ID']}",
    )


def _get_country(connection: Connection, country_name: str) -> dict:
    country = connection.execute(
        text(
            '''
            SELECT *
            FROM countries
            WHERE "Name" IN :country_variants
            LIMIT 1
            '''
        ).bindparams(bindparam("country_variants", expanding=True)),
        {"country_variants": tuple(_country_name_variants(country_name))},
    ).mappings().first()
    if country is None:
        raise HTTPException(status_code=404, detail=f"Country {country_name} not found")
    return dict(country)


def _total_transfer_market_value(connection: Connection, team_name: str) -> float:
    total_value = connection.execute(
        text(
            '''
            SELECT COALESCE(SUM("Market_Value"), 0)
            FROM players
            WHERE "Country" IN :country_variants
            '''
        ).bindparams(bindparam("country_variants", expanding=True)),
        {"country_variants": tuple(_country_name_variants(team_name))},
    ).scalar_one()
    return float(total_value or 0.0)


def _has_home_advantage(team_name: str, stadium_name: str) -> bool:
    team_variants = _country_name_variants(team_name)
    return any(stadium_name in HOME_COUNTRY_STADIUMS.get(team, set()) for team in team_variants)


def _days_rested(connection: Connection, match: dict, team_name: str) -> int | str | None:
    previous_match = _previous_played_match(connection, int(match["Match_ID"]), team_name)
    if previous_match is None:
        return "No games played in WC before yet."

    match_date = _parse_match_date(match.get("Date"))
    previous_date = _parse_match_date(previous_match.get("Date"))
    if match_date is None or previous_date is None:
        return None

    return int((match_date - previous_date).days)


def _previous_played_match(connection: Connection, match_id: int, team_name: str) -> dict | None:
    previous_match = connection.execute(
        text(
            '''
            SELECT *
            FROM matches
            WHERE "Match_ID" < :match_id
              AND ("Team_A" = :team OR "Team_B" = :team)
              AND "Goals_A" IS NOT NULL
              AND "Goals_B" IS NOT NULL
              AND CAST("Goals_A" AS TEXT) != ''
              AND CAST("Goals_B" AS TEXT) != ''
            ORDER BY "Match_ID" DESC
            LIMIT 1
            '''
        ),
        {"match_id": int(match_id), "team": team_name},
    ).mappings().first()
    return dict(previous_match) if previous_match is not None else None


def _parse_match_date(value):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed


def _base_camp_travel_distance_km(connection: Connection, match: dict, country: dict) -> float:
    base_camp = _get_location_by_name(connection, str(country["Base_Camp_City"]))
    stadium = _get_location_by_name(connection, str(match["Stadium_Name"]))
    distance_km = _haversine_km(
        base_camp["Latitude"],
        base_camp["Longitude"],
        stadium["Latitude"],
        stadium["Longitude"],
    )
    return round(distance_km, 2)


def _get_location_by_name(connection: Connection, location_name: str) -> dict:
    location = connection.execute(
        text('SELECT * FROM locations WHERE "Location_Name" = :location_name'),
        {"location_name": location_name},
    ).mappings().first()
    if location is None:
        raise HTTPException(status_code=404, detail=f"Location {location_name} not found")
    return dict(location)


def _haversine_km(lat_a: object, lon_a: object, lat_b: object, lon_b: object) -> float:
    lat_a = radians(float(lat_a))
    lon_a = radians(float(lon_a))
    lat_b = radians(float(lat_b))
    lon_b = radians(float(lon_b))

    lat_delta = lat_b - lat_a
    lon_delta = lon_b - lon_a
    haversine = (
        sin(lat_delta / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(lon_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))


def _get_match(engine: Engine, match_id: int) -> dict:
    with engine.connect() as connection:
        match = connection.execute(
            text('SELECT * FROM matches WHERE "Match_ID" = :match_id'),
            {"match_id": int(match_id)},
        ).mappings().first()
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return dict(match)


def _ensure_group_predictions_available(engine: Engine) -> None:
    with engine.connect() as connection:
        missing_prediction = connection.execute(
            text(
                '''
                SELECT 1
                FROM matches
                WHERE "Match_Type" = 'Group'
                  AND ("Predicted_Goals_A" IS NULL OR "Predicted_Goals_B" IS NULL)
                LIMIT 1
                '''
            )
        ).scalar()
    if missing_prediction is not None:
        run_predictions_for_matches(engine, 1, 72)


def _dataframe_records(dataframe: pd.DataFrame) -> list[dict]:
    return _sanitize(dataframe.to_dict(orient="records"))


def _sanitize(value):
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if pd.isna(value):
        return None
    # Add this check to handle NumPy int64/float64 serialization
    if hasattr(value, "item"):  
        return value.item()
    return value


def _is_missing(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""
