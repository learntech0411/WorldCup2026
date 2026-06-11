from pathlib import Path
import os
import sys

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import get_engine
from app.predictions import (
    prediction_final_rounds,
    prediction_round_of_32,
    run_predictions_for_matches,
    set_real_round_of_32_participants_and_run_prediction,
)
from app.utilities import (
    calculate_all_group_score_matrices,
    calculate_base_strengths,
    calculate_total_utility_values,
    pretty_print_group_score_matrices,
)
from data_scrapper import scrape_countries_data, scrape_world_cup_players


def run_full_prediction_pipeline(db: Engine = None) -> None:
    db = _engine_or_default(db)
    calculate_total_utility_values(db, stage="group")
    calculate_base_strengths(db)
    run_predictions_for_matches(db, 1, 72)
    matrices = calculate_all_group_score_matrices(db, "Prediction")
    pretty_print_group_score_matrices(matrices)
    prediction_round_of_32(db)
    prediction_final_rounds(db, 89)

def update_during_group_match(db: Engine = None) -> None:
    db = _engine_or_default(db)
    #
    update_player_injuries(db)
    refresh_elo_ratings(db)
    calculate_total_utility_values(db, stage="group")
    calculate_base_strengths(db)
    run_predictions_for_matches(db, 1, 72)
    matrices = calculate_all_group_score_matrices(db, "Prediction")
    pretty_print_group_score_matrices(matrices)
    prediction_round_of_32(db)
    prediction_final_rounds(db, 89)

def run_once_after_group_stage(db: Engine = None) -> None:
    db = _engine_or_default(db)
    round_of_32_participants = [] # create dict where key is match id and value is tuple of strings containing (Team_A, Team_B)
    set_real_round_of_32_participants_and_run_prediction(db, round_of_32_participants)

def update_during_knockout_match(db: Engine = None) -> None:
    db = _engine_or_default(db)
    #
    update_player_injuries(db)
    refresh_elo_ratings(db)
    calculate_total_utility_values(db, stage="group")
    calculate_base_strengths(db)
    run_predictions_for_matches(db, 73, 88)
    prediction_final_rounds(db, 89)

def post_match_update(
    match_id: int,
    score_a: int,
    score_b: int,
    injured_players_list: list[object] = None,
    stage: str = "group",
    db: Engine = None,
) -> None:
    """Update a completed match and refresh downstream ratings/predictions."""
    db = _engine_or_default(db)
    injured_players_list = injured_players_list or []

    with db.begin() as connection:
        _upsert_match_result(connection, match_id, score_a, score_b)
        _mark_injured_players(connection, injured_players_list)

    refresh_elo_ratings(db)
    calculate_total_utility_values(db, stage=stage)
    calculate_base_strengths(db)

    lowest_match_id = _lowest_unplayed_match_id(db)
    if lowest_match_id is None:
        return

    if lowest_match_id < 73:
        run_predictions_for_matches(db, lowest_match_id, 72)
        _reset_match_placeholders(db, 73, 104)
        prediction_round_of_32(db)
        prediction_final_rounds(db, 89)
    elif lowest_match_id < 89:
        run_predictions_for_matches(db, lowest_match_id, 88)
        _reset_match_placeholders(db, 89, 104)
        prediction_final_rounds(db, 89)
    else:
        _reset_match_placeholders(db, lowest_match_id, 104)
        prediction_final_rounds(db, lowest_match_id)


def refresh_elo_ratings(db: Engine = None) -> None:
    """Scrape current Elo ratings and update countries.Base_Elo."""
    db = _engine_or_default(db)

    original_cwd = Path.cwd()
    try:
        os.chdir(BACKEND_DIR)
        countries = scrape_countries_data()
    finally:
        os.chdir(original_cwd)

    if countries is None or countries.empty:
        return

    update_rows = [
        {"name": row.Name, "base_elo": float(row.Base_Elo)}
        for row in countries[["Name", "Base_Elo"]].itertuples(index=False)
    ]

    if not update_rows:
        return

    with db.begin() as connection:
        connection.execute(
            text(
                '''
                UPDATE countries
                SET "Base_Elo" = :base_elo
                WHERE "Name" = :name
                '''
            ),
            update_rows,
        )


def update_player_injuries(db: Engine = None) -> None:
    """Refresh scraped player injuries and update changed rows in players."""
    db = _engine_or_default(db)

    with db.connect() as connection:
        players = pd.read_sql_query(
            text('SELECT "Name", "Country", "Is_Injured" FROM players'),
            connection,
        )

    if players.empty:
        return

    original_cwd = Path.cwd()
    try:
        os.chdir(BACKEND_DIR)
        scraped_players = scrape_world_cup_players()
    finally:
        os.chdir(original_cwd)

    if scraped_players is None or scraped_players.empty:
        return

    scraped_players = scraped_players[["Name", "Country", "Is_Injured"]].copy()
    players["Is_Injured"] = players["Is_Injured"].map(_normalize_bool)
    scraped_players["Is_Injured"] = scraped_players["Is_Injured"].map(_normalize_bool)

    changed_players = players.merge(
        scraped_players,
        on=["Name", "Country"],
        how="inner",
        suffixes=("_current", "_scraped"),
    )
    changed_players = changed_players[
        changed_players["Is_Injured_current"] != changed_players["Is_Injured_scraped"]
    ]

    if changed_players.empty:
        return

    update_rows = [
        {
            "name": row.Name,
            "country": row.Country,
            "is_injured": bool(row.Is_Injured_scraped),
        }
        for row in changed_players.itertuples(index=False)
    ]

    with db.begin() as connection:
        connection.execute(
            text(
                '''
                UPDATE players
                SET "Is_Injured" = :is_injured
                WHERE "Name" = :name
                  AND "Country" = :country
                '''
            ),
            update_rows,
        )


def reset_goals_from_matches(match_ids: list[int], db: Engine = None) -> None:
    """Reset actual scores for the given matches."""
    db = _engine_or_default(db)
    if not match_ids:
        return

    with db.begin() as connection:
        injured_column = _match_injured_players_column(connection)
        assignments = ['"Goals_A" = NULL', '"Goals_B" = NULL']
        if injured_column is not None:
            assignments.append(f'"{injured_column}" = NULL')

        for match_id in match_ids:
            connection.execute(
                text(
                    f'''
                    UPDATE matches
                    SET {", ".join(assignments)}
                    WHERE "Match_ID" = :match_id
                    '''
                ),
                {"match_id": int(match_id)},
            )


def reset_knockout_stage_matches(match_ids: list[int] = None, db: Engine = None) -> None:
    """Reset knockout teams and prediction columns for selected or all knockout matches."""
    db = _engine_or_default(db)

    reset_columns = [
        "Team_A",
        "Team_B",
        "Predicted_Goals_A",
        "Predicted_Goals_B",
        "Winning_Probability_A",
        "Winning_Probability_B",
        "Draw_Probability",
    ]
    assignments = ", ".join(f'"{column}" = NULL' for column in reset_columns)

    with db.begin() as connection:
        if match_ids:
            for match_id in match_ids:
                connection.execute(
                    text(
                        f'''
                        UPDATE matches
                        SET {assignments}
                        WHERE "Match_ID" = :match_id
                          AND "Match_Type" = 'Knockout'
                        '''
                    ),
                    {"match_id": int(match_id)},
                )
        else:
            connection.execute(
                text(
                    f'''
                    UPDATE matches
                    SET {assignments}
                    WHERE "Match_Type" = 'Knockout'
                    '''
                )
            )


def _upsert_match_result(connection, match_id: int, score_a: int, score_b: int) -> None:
    updated = connection.execute(
        text(
            '''
            UPDATE matches
            SET "Goals_A" = :score_a,
                "Goals_B" = :score_b
            WHERE "Match_ID" = :match_id
            '''
        ),
        {
            "match_id": int(match_id),
            "score_a": int(score_a),
            "score_b": int(score_b),
        },
    )

    if updated.rowcount == 0:
        connection.execute(
            text(
                '''
                INSERT INTO matches ("Match_ID", "Goals_A", "Goals_B")
                VALUES (:match_id, :score_a, :score_b)
                '''
            ),
            {
                "match_id": int(match_id),
                "score_a": int(score_a),
                "score_b": int(score_b),
            },
        )


def _mark_injured_players(connection, injured_players_list: list[object]) -> None:
    for player in injured_players_list:
        if isinstance(player, int) or (isinstance(player, str) and player.isdigit()):
            connection.execute(
                text(
                    '''
                    UPDATE players
                    SET "Is_Injured" = TRUE
                    WHERE "Player_ID" = :player_id
                    '''
                ),
                {"player_id": int(player)},
            )
        else:
            connection.execute(
                text(
                    '''
                    UPDATE players
                    SET "Is_Injured" = TRUE
                    WHERE "Name" = :player_name
                    '''
                ),
                {"player_name": str(player)},
            )


def _lowest_unplayed_match_id(db: Engine) -> int | None:
    with db.connect() as connection:
        result = connection.execute(
            text(
                '''
                SELECT "Match_ID"
                FROM matches
                WHERE "Goals_A" IS NULL
                   OR "Goals_B" IS NULL
                   OR CAST("Goals_A" AS TEXT) = ''
                   OR CAST("Goals_B" AS TEXT) = ''
                ORDER BY "Match_ID"
                LIMIT 1
                '''
            )
        ).scalar()

    return int(result) if result is not None else None


def _reset_match_placeholders(db: Engine, starting_match_id: int, ending_match_id: int) -> None:
    template_matches = pd.read_csv(BACKEND_DIR / "world_cup_matches.csv")
    template_matches = template_matches[
        (template_matches["Match_ID"] >= starting_match_id)
        & (template_matches["Match_ID"] <= ending_match_id)
    ]

    with db.begin() as connection:
        for match in template_matches.itertuples(index=False):
            connection.execute(
                text(
                    '''
                    UPDATE matches
                    SET "Team_A" = :team_a,
                        "Team_B" = :team_b,
                        "Predicted_Goals_A" = NULL,
                        "Predicted_Goals_B" = NULL,
                        "Winning_Probability_A" = NULL,
                        "Winning_Probability_B" = NULL,
                        "Draw_Probability" = NULL
                    WHERE "Match_ID" = :match_id
                    '''
                ),
                {
                    "match_id": int(match.Match_ID),
                    "team_a": str(match.Team_A),
                    "team_b": str(match.Team_B),
                },
            )


def _match_injured_players_column(connection) -> str | None:
    possible_names = {"Injured_Players", "injured_players", "InjuredPlayers"}
    existing_columns = {column["name"] for column in inspect(connection).get_columns("matches")}
    matching_columns = possible_names & existing_columns
    return sorted(matching_columns)[0] if matching_columns else None


def _normalize_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "t", "1", "yes", "y"}
    return bool(value)


def _engine_or_default(db: Engine = None) -> Engine:
    if db is not None:
        return db
    return get_engine()


if __name__ == "__main__":
    run_full_prediction_pipeline()
