import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.database import get_engine
from app.predictions import run_predictions_for_matches, winner_prediction
from app.utilities import calculate_all_group_score_matrices, calculate_match_power_score


router = APIRouter(prefix="/api", tags=["frontend-data"])


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
