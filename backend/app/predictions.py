from math import exp, factorial
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.utilities import (
    calculate_all_group_score_matrices,
    calculate_match_power_score,
    get_third_place_opponents_dict,
)


BASE_EXPECTED_GOALS = 1.3
ELO_XG_SCALE = 600.0
MIN_EXPECTED_GOALS = 0.5
MAX_EXPECTED_GOALS = 4.0
MAX_GOALS_IN_MATRIX = 7
DIXON_COLES_RHO = 0.07
BACKEND_DIR = Path(__file__).resolve().parents[1]


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
        selected_matches = connection.execute(
            text(
                '''
                SELECT *
                FROM matches
                WHERE "Match_ID" BETWEEN :starting_match_id AND :ending_match_id
                  AND (
                    "Goals_A" IS NULL
                    OR "Goals_B" IS NULL
                    OR CAST("Goals_A" AS TEXT) = ''
                    OR CAST("Goals_B" AS TEXT) = ''
                  )
                ORDER BY "Match_ID"
                '''
            ),
            {
                "starting_match_id": int(starting_match_id),
                "ending_match_id": int(ending_match_id),
            },
        ).mappings().all()
        if not selected_matches:
            if transaction is not None:
                transaction.commit()
            _commit_if_session(db)
            return _empty_prediction_result()

        predictions = []
        for match in selected_matches:
            match_id = int(match["Match_ID"])
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


def prediction_round_of_32(db: Session | Connection | Engine) -> pd.DataFrame:
    """Fill Round of 32 teams, then run predictions for matches 73-88."""
    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        group_score_matrices = calculate_all_group_score_matrices(connection, "Prediction")
        third_place_opponents = get_third_place_opponents_dict(connection)
        matches = connection.execute(
            text('SELECT * FROM matches WHERE "Match_ID" BETWEEN 73 AND 88 ORDER BY "Match_ID"')
        ).mappings().all()

        updates = []
        for match in matches:
            original_team_a = str(match["Team_A"])
            original_team_b = str(match["Team_B"])
            team_a = _resolve_round_of_32_slot(original_team_a, group_score_matrices)
            team_b = _resolve_round_of_32_slot(original_team_b, group_score_matrices)

            if original_team_a.startswith("1") and original_team_b.startswith("3"):
                third_place_slot = third_place_opponents.get(original_team_a)
                if third_place_slot is None:
                    raise ValueError(f"No third-place opponent option found for {original_team_a}")
                team_b = _resolve_round_of_32_slot(third_place_slot, group_score_matrices)
            
            # Add this missing block to handle when Team B is the 1st place team
            elif original_team_b.startswith("1") and original_team_a.startswith("3"):
                third_place_slot = third_place_opponents.get(original_team_b)
                if third_place_slot is None:
                    raise ValueError(f"No third-place opponent option found for {original_team_b}")
                team_a = _resolve_round_of_32_slot(third_place_slot, group_score_matrices)
                
            updates.append(
                {
                    "match_id": int(match["Match_ID"]),
                    "team_a": team_a,
                    "team_b": team_b,
                }
            )

        _update_round_of_32_teams(connection, updates)
        predictions = run_predictions_for_matches(connection, 73, 88)

        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return predictions
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def prediction_final_rounds(
    db: Session | Connection | Engine,
    match_id: int,
) -> pd.DataFrame:
    """Fill knockout rounds after the Round of 32 and run predictions round by round."""
    round_endings = [96, 100, 102, 104]
    starting_id = int(match_id)
    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        all_predictions = []
        while starting_id <= round_endings[-1]:
            ending_id = _next_round_ending(starting_id, round_endings)
            _fill_final_round_teams(connection, starting_id, ending_id)
            predictions = run_predictions_for_matches(connection, starting_id, ending_id)
            if not predictions.empty:
                all_predictions.append(predictions)

            if ending_id >= round_endings[-1]:
                break
            starting_id = ending_id + 1

        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return pd.concat(all_predictions, ignore_index=True) if all_predictions else _empty_prediction_result()
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def set_real_round_of_32_participants_and_run_prediction(
    db: Session | Connection | Engine,
    round_of_32_participants: dict[int, tuple[str, str]],
) -> pd.DataFrame:
    """Set real Round of 32 teams, then rerun Round of 32 and later predictions."""
    if not round_of_32_participants:
        raise ValueError("round_of_32_participants cannot be empty")

    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        smallest_match_id = min(int(match_id) for match_id in round_of_32_participants)
        _reset_knockout_matches(connection, smallest_match_id)
        _set_round_of_32_participants(connection, round_of_32_participants)

        round_of_32_predictions = run_predictions_for_matches(connection, 73, 88)
        final_round_predictions = prediction_final_rounds(connection, 89)

        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        if final_round_predictions.empty:
            return round_of_32_predictions
        if round_of_32_predictions.empty:
            return final_round_predictions
        return pd.concat([round_of_32_predictions, final_round_predictions], ignore_index=True)
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


def _reset_knockout_matches(connection: Connection, starting_match_id: int | None = None) -> None:
    statement = '''
        UPDATE matches
        SET "Team_A" = NULL,
            "Team_B" = NULL,
            "Predicted_Goals_A" = NULL,
            "Predicted_Goals_B" = NULL,
            "Winning_Probability_A" = NULL,
            "Winning_Probability_B" = NULL,
            "Draw_Probability" = NULL
        WHERE "Match_Type" = 'Knockout'
    '''

    if starting_match_id is not None:
        statement += '\n          AND "Match_ID" >= :starting_match_id'
        connection.execute(text(statement), {"starting_match_id": int(starting_match_id)})
        return

    connection.execute(text(statement))


def _set_round_of_32_participants(
    connection: Connection,
    round_of_32_participants: dict[int, tuple[str, str]],
) -> None:
    updates = []
    for match_id, teams in round_of_32_participants.items():
        if len(teams) != 2:
            raise ValueError(f"Match {match_id} must have a (Team_A, Team_B) tuple")
        updates.append(
            {
                "match_id": int(match_id),
                "team_a": str(teams[0]),
                "team_b": str(teams[1]),
            }
        )

    _update_round_of_32_teams(connection, updates)


def _next_round_ending(starting_id: int, round_endings: list[int]) -> int:
    for ending_id in round_endings:
        if ending_id >= starting_id:
            return ending_id
    return round_endings[-1]


def _fill_final_round_teams(connection: Connection, starting_id: int, ending_id: int) -> None:
    country_names = {
        str(row["Name"])
        for row in connection.execute(text('SELECT "Name" FROM countries')).mappings()
    }
    round_matches = connection.execute(
        text(
            '''
            SELECT *
            FROM matches
            WHERE "Match_ID" BETWEEN :starting_id AND :ending_id
            ORDER BY "Match_ID"
            '''
        ),
        {
            "starting_id": int(starting_id),
            "ending_id": int(ending_id),
        },
    ).mappings().all()

    updates = []
    for match in round_matches:
        team_a = _resolve_final_round_team(connection, str(match["Team_A"]), country_names)
        team_b = _resolve_final_round_team(connection, str(match["Team_B"]), country_names)
        updates.append(
            {
                "match_id": int(match["Match_ID"]),
                "team_a": team_a,
                "team_b": team_b,
            }
        )

    _update_round_of_32_teams(connection, updates)


def _resolve_final_round_team(connection: Connection, team_value: str, country_names: set[str]) -> str:
    if team_value in country_names:
        return team_value

    marker = team_value[:1]
    source_match_id = team_value[1:]
    if marker not in {"W", "L"} or not source_match_id.isdigit():
        return team_value

    source_match = connection.execute(
        text('SELECT * FROM matches WHERE "Match_ID" = :match_id'),
        {"match_id": int(source_match_id)},
    ).mappings().first()
    if source_match is None:
        raise ValueError(f"Source match not found for slot {team_value}")

    winner, loser = _predicted_winner_and_loser(source_match)
    return winner if marker == "W" else loser


def _predicted_winner_and_loser(match: pd.Series) -> tuple[str, str]:
    team_a = str(match["Team_A"])
    team_b = str(match["Team_B"])
    goals_a = pd.to_numeric(match["Predicted_Goals_A"], errors="coerce")
    goals_b = pd.to_numeric(match["Predicted_Goals_B"], errors="coerce")

    if pd.isna(goals_a) or pd.isna(goals_b):
        raise ValueError(f"Match {match['Match_ID']} does not have predicted goals yet")

    if goals_a > goals_b:
        return team_a, team_b
    if goals_b > goals_a:
        return team_b, team_a

    probability_a = pd.to_numeric(match["Winning_Probability_A"], errors="coerce")
    probability_b = pd.to_numeric(match["Winning_Probability_B"], errors="coerce")
    if not pd.isna(probability_a) and not pd.isna(probability_b) and probability_a != probability_b:
        return (team_a, team_b) if probability_a > probability_b else (team_b, team_a)

    return team_a, team_b


def _resolve_round_of_32_slot(slot: str, group_score_matrices: dict[str, pd.DataFrame]) -> str:
    slot = str(slot)
    if len(slot) != 2:
        return slot

    rank_marker = slot[0]
    group_name = slot[1]
    if rank_marker not in {"1", "2", "3"}:
        return slot

    return _team_from_group_rank(group_score_matrices, group_name, int(rank_marker))


def _team_from_group_rank(
    group_score_matrices: dict[str, pd.DataFrame],
    group_name: str,
    rank: int,
) -> str:
    if group_name not in group_score_matrices:
        raise ValueError(f"Group not found in score matrix: {group_name}")

    group_table = group_score_matrices[group_name]
    team_row = group_table[group_table["Rank"] == rank]
    if team_row.empty:
        raise ValueError(f"Rank {rank} not found for Group {group_name}")

    return str(team_row.iloc[0]["Team"])


def _update_round_of_32_teams(connection: Connection, updates: list[dict[str, object]]) -> None:
    if not updates:
        return

    connection.execute(
        text(
            '''
            UPDATE matches
            SET "Team_A" = :team_a,
                "Team_B" = :team_b
            WHERE "Match_ID" = :match_id
            '''
        ),
        updates,
    )


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
