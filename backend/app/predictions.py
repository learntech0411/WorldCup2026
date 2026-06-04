from math import exp, factorial
from typing import Optional

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.utilities import calculate_match_power_score


BASE_EXPECTED_GOALS = 1.35
ELO_XG_SCALE = 800.0
MIN_EXPECTED_GOALS = 0.2
MAX_EXPECTED_GOALS = 4.5
MAX_GOALS_IN_MATRIX = 10
DIXON_COLES_RHO = -0.10


def winner_prediction(
    db: Session | Connection | Engine,
    match_id: int,
    match_power_score_a: float,
    match_power_score_b: float,
) -> dict[str, float]:
    """Predict a match result and update the Matches table."""
    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        _ensure_prediction_columns(connection)

        xg_a, xg_b = _expected_goals(match_power_score_a, match_power_score_b)
        probability_matrix = _dixon_coles_matrix(xg_a, xg_b)
        prediction = _summarize_probability_matrix(probability_matrix)

        _update_match_prediction(
            connection,
            match_id,
            prediction["Predicted_Goals_A"],
            prediction["Predicted_Goals_B"],
            prediction["Winning_Probability_A"],
            prediction["Winning_Probability_B"],
            prediction["Draw_Probability"],
        )

        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return {
            "Match_ID": int(match_id),
            "Expected_Goals_A": float(xg_a),
            "Expected_Goals_B": float(xg_b),
            **prediction,
        }
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def run_predictions_for_matches(
    db: Session | Connection | Engine,
    starting_match_id: int,
    ending_match_id: int,
) -> pd.DataFrame:
    """Run predictions for unplayed matches in a Match_ID range."""
    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        matches = pd.read_sql_query(text('SELECT * FROM matches'), connection)
        if matches.empty:
            if transaction is not None:
                transaction.commit()
            _commit_if_session(db)
            return _empty_prediction_result()

        matches["Match_ID_Numeric"] = pd.to_numeric(matches["Match_ID"], errors="coerce")
        selected_matches = matches[
            (matches["Match_ID_Numeric"] >= starting_match_id)
            & (matches["Match_ID_Numeric"] <= ending_match_id)
            & matches["Goals_A"].apply(_is_missing_score)
            & matches["Goals_B"].apply(_is_missing_score)
        ].sort_values("Match_ID_Numeric")

        predictions = []
        for match in selected_matches.itertuples(index=False):
            match_id = int(match.Match_ID)
            power_score = calculate_match_power_score(connection, match_id)
            prediction = winner_prediction(
                connection,
                match_id,
                power_score["Match_Power_Score_A"],
                power_score["Match_Power_Score_B"],
            )
            predictions.append({**power_score, **prediction})

        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return pd.DataFrame(predictions) if predictions else _empty_prediction_result()
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def _expected_goals(match_power_score_a: float, match_power_score_b: float) -> tuple[float, float]:
    score_difference = match_power_score_a - match_power_score_b
    xg_a = BASE_EXPECTED_GOALS * exp(score_difference / ELO_XG_SCALE)
    xg_b = BASE_EXPECTED_GOALS * exp(-score_difference / ELO_XG_SCALE)
    return _clamp(xg_a, MIN_EXPECTED_GOALS, MAX_EXPECTED_GOALS), _clamp(
        xg_b,
        MIN_EXPECTED_GOALS,
        MAX_EXPECTED_GOALS,
    )


def _dixon_coles_matrix(xg_a: float, xg_b: float) -> dict[tuple[int, int], float]:
    matrix = {}
    for goals_a in range(MAX_GOALS_IN_MATRIX + 1):
        probability_a = _poisson_probability(goals_a, xg_a)
        for goals_b in range(MAX_GOALS_IN_MATRIX + 1):
            probability_b = _poisson_probability(goals_b, xg_b)
            adjustment = _dixon_coles_adjustment(goals_a, goals_b, xg_a, xg_b)
            matrix[(goals_a, goals_b)] = probability_a * probability_b * adjustment

    total_probability = sum(matrix.values())
    if total_probability <= 0:
        raise ValueError("Dixon-Coles matrix produced no probability mass")

    return {
        score: probability / total_probability
        for score, probability in matrix.items()
    }


def _summarize_probability_matrix(matrix: dict[tuple[int, int], float]) -> dict[str, float]:
    winning_probability_a = sum(
        probability
        for (goals_a, goals_b), probability in matrix.items()
        if goals_a > goals_b
    )
    winning_probability_b = sum(
        probability
        for (goals_a, goals_b), probability in matrix.items()
        if goals_b > goals_a
    )
    draw_probability = sum(
        probability
        for (goals_a, goals_b), probability in matrix.items()
        if goals_a == goals_b
    )
    predicted_goals_a, predicted_goals_b = max(matrix, key=matrix.get)

    return {
        "Predicted_Goals_A": float(predicted_goals_a),
        "Predicted_Goals_B": float(predicted_goals_b),
        "Winning_Probability_A": float(winning_probability_a),
        "Winning_Probability_B": float(winning_probability_b),
        "Draw_Probability": float(draw_probability),
    }


def _dixon_coles_adjustment(goals_a: int, goals_b: int, xg_a: float, xg_b: float) -> float:
    if goals_a == 0 and goals_b == 0:
        return 1 - (xg_a * xg_b * DIXON_COLES_RHO)
    if goals_a == 0 and goals_b == 1:
        return 1 + (xg_a * DIXON_COLES_RHO)
    if goals_a == 1 and goals_b == 0:
        return 1 + (xg_b * DIXON_COLES_RHO)
    if goals_a == 1 and goals_b == 1:
        return 1 - DIXON_COLES_RHO
    return 1.0


def _poisson_probability(goals: int, expected_goals: float) -> float:
    return (expected_goals**goals * exp(-expected_goals)) / factorial(goals)


def _update_match_prediction(
    connection: Connection,
    match_id: int,
    predicted_goals_a: float,
    predicted_goals_b: float,
    winning_probability_a: float,
    winning_probability_b: float,
    draw_probability: float,
) -> None:
    connection.execute(
        text(
            '''
            UPDATE matches
            SET "Predicted_Goals_A" = :predicted_goals_a,
                "Predicted_Goals_B" = :predicted_goals_b,
                "Winning_Probability_A" = :winning_probability_a,
                "Winning_Probability_B" = :winning_probability_b,
                "Draw_Probability" = :draw_probability
            WHERE "Match_ID" = :match_id
            '''
        ),
        {
            "match_id": int(match_id),
            "predicted_goals_a": float(predicted_goals_a),
            "predicted_goals_b": float(predicted_goals_b),
            "winning_probability_a": float(winning_probability_a),
            "winning_probability_b": float(winning_probability_b),
            "draw_probability": float(draw_probability),
        },
    )


def _ensure_prediction_columns(connection: Connection) -> None:
    for column_name in (
        "Predicted_Goals_A",
        "Predicted_Goals_B",
        "Winning_Probability_A",
        "Winning_Probability_B",
        "Draw_Probability",
    ):
        _ensure_column(connection, "matches", column_name, "FLOAT")


def _ensure_column(connection: Connection, table_name: str, column_name: str, column_type: str) -> None:
    existing_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name not in existing_columns:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {column_type};'))


def _get_connection(db: Session | Connection | Engine) -> Connection:
    if isinstance(db, Session):
        return db.connection()
    if isinstance(db, Engine):
        return db.connect()
    return db


def _commit_if_session(db: Session | Connection | Engine) -> None:
    if isinstance(db, Session):
        db.commit()


def _is_missing_score(value: object) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _empty_prediction_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Match_ID",
            "Team_A",
            "Team_B",
            "Match_Power_Score_A",
            "Match_Power_Score_B",
            "Expected_Goals_A",
            "Expected_Goals_B",
            "Predicted_Goals_A",
            "Predicted_Goals_B",
            "Winning_Probability_A",
            "Winning_Probability_B",
            "Draw_Probability",
        ]
    )
