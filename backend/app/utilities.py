from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


Stage = Literal["group", "knockout"]

AGE_MULTIPLIERS = {
    "young": 0.70,
    "peak": 1.00,
    "experienced": 1.15,
    "veteran": 1.00,
}

POSITION_MULTIPLIERS = {
    "Attacker": 0.85,
    "Midfielder": 1.00,
    "Defender": 1.25,
    "Goalkeeper": 1.50,
}

FREE_AGENT_NAMES = {"", "free agent", "no club", "none", "unattached", "nan"}


def calculate_total_utility_values(
    db: Session | Connection | Engine,
    *,
    stage: Stage = "group",
    output_csv_path: Optional[str | Path] = None,
) -> pd.DataFrame:
    """Calculate player utility values and update country total utility values.

    Args:
        db: SQLAlchemy Session, Connection, or Engine connected to the app database.
        stage: Tournament phase. Controls the rank-16 multiplier.
        output_csv_path: Optional CSV output path. Defaults to backend/value_transform.csv.

    Returns:
        A DataFrame containing the player-level value transformation details.
    """
    if stage not in {"group", "knockout"}:
        raise ValueError("stage must be either 'group' or 'knockout'")

    output_path = Path(output_csv_path) if output_csv_path else _default_output_path()

    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        _ensure_column(connection, "players", "Expected_Utility_Value", "FLOAT")
        _ensure_column(connection, "countries", "Total_Utility_Value", "FLOAT DEFAULT 0")

        players = pd.read_sql_query(text('SELECT * FROM players'), connection)
        if players.empty:
            empty_result = _empty_result()
            empty_result.to_csv(output_path, index=False)
            if transaction is not None:
                transaction.commit()
            _commit_if_session(db)
            return empty_result

        players = _calculate_player_values(players, stage)
        transform = players[
            [
                "Name",
                "Country",
                "Market_Value",
                "Age_Mult",
                "Position_Mult",
                "Rank_Mult",
                "Synergy_Mult",
                "Expected_Utility_Value",
            ]
        ].rename(columns={"Name": "Player_Name"})
        transform = transform.sort_values(["Country", "Expected_Utility_Value"], ascending=[True, False])
        transform.to_csv(output_path, index=False)

        totals = (
            transform.groupby("Country", as_index=False)["Expected_Utility_Value"]
            .sum()
            .rename(columns={"Expected_Utility_Value": "Total_Utility_Value"})
        )

        _update_player_utility_values(connection, players)
        _update_country_totals(connection, totals)
        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return transform
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def _calculate_player_values(players: pd.DataFrame, stage: Stage) -> pd.DataFrame:
    players = players.copy()
    players["Age_Mult"] = players["Age"].apply(_age_multiplier)
    players["Position_Mult"] = players["Model_Position"].apply(_position_multiplier)
    players["Is_Injured_Normalized"] = players["Is_Injured"].apply(_is_injured)
    players["Market_Value"] = pd.to_numeric(players["Market_Value"], errors="coerce").fillna(0.0)
    players["Temp_Capability"] = players["Market_Value"] * players["Age_Mult"] * players["Position_Mult"]
    players.loc[players["Is_Injured_Normalized"], "Temp_Capability"] = 0.0
    players["Rank_Mult"] = 0.0
    players["Synergy_Mult"] = 1.0

    for _, country_players in players.groupby("Country", sort=False):
        country_index = country_players.index
        available = country_players[~country_players["Is_Injured_Normalized"]]

        goalkeepers = available[available["Model_Position"] == "Goalkeeper"].sort_values(
            ["Temp_Capability", "Market_Value", "Name"],
            ascending=[False, False, True],
        )
        if not goalkeepers.empty:
            top_goalkeeper_index = goalkeepers.index[0]
            players.loc[goalkeepers.index, "Rank_Mult"] = 0.1
            players.loc[top_goalkeeper_index, "Rank_Mult"] = 1.0
        else:
            top_goalkeeper_index = None

        outfield = available[available["Model_Position"] != "Goalkeeper"].sort_values(
            ["Temp_Capability", "Market_Value", "Name"],
            ascending=[False, False, True],
        )
        for rank, player_index in enumerate(outfield.index, start=1):
            players.loc[player_index, "Rank_Mult"] = _rank_multiplier(rank, stage)

        synergy_indexes = []
        if top_goalkeeper_index is not None:
            synergy_indexes.append(top_goalkeeper_index)
        synergy_indexes.extend(outfield.head(15).index.tolist())
        _apply_synergy(players, synergy_indexes)

        injured_index = country_players[country_players["Is_Injured_Normalized"]].index
        players.loc[injured_index, ["Temp_Capability", "Rank_Mult"]] = 0.0
        players.loc[country_index, "Expected_Utility_Value"] = (
            players.loc[country_index, "Temp_Capability"]
            * players.loc[country_index, "Rank_Mult"]
            * players.loc[country_index, "Synergy_Mult"]
        )

    return players


def _age_multiplier(age: object) -> float:
    if pd.isna(age):
        return 1.0

    age = int(age)
    if 17 <= age <= 22:
        return AGE_MULTIPLIERS["young"]
    if 23 <= age <= 29:
        return AGE_MULTIPLIERS["peak"]
    if 30 <= age <= 33:
        return AGE_MULTIPLIERS["experienced"]
    if age >= 34:
        return AGE_MULTIPLIERS["veteran"]
    return 1.0


def _position_multiplier(position: object) -> float:
    return POSITION_MULTIPLIERS.get(str(position), 1.0)


def _rank_multiplier(rank: int, stage: Stage) -> float:
    if rank <= 10:
        return 1.0
    if rank <= 15:
        return 0.8
    if rank == 16:
        return 0.6 if stage == "knockout" else 0.4
    if rank <= 21:
        return 0.4
    return 0.1


def _apply_synergy(players: pd.DataFrame, player_indexes: list[int]) -> None:
    if not player_indexes:
        return

    synergy_players = players.loc[player_indexes].copy()
    synergy_players["Club_Key"] = synergy_players["Club"].apply(_club_key)
    for club_key, club_group in synergy_players.groupby("Club_Key"):
        if _is_free_agent(club_key):
            synergy_mult = 1.0
        else:
            synergy_mult = _synergy_multiplier(len(club_group))
        players.loc[club_group.index, "Synergy_Mult"] = synergy_mult


def _synergy_multiplier(group_size: int) -> float:
    if group_size <= 1:
        return 1.0
    if group_size == 2:
        return 1.02
    if group_size == 3:
        return 1.04
    if group_size == 4:
        return 1.06
    if group_size == 5:
        return 1.08
    return 1.10


def _is_injured(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _club_key(club: object) -> str:
    if pd.isna(club):
        return ""
    return str(club).strip()


def _is_free_agent(club_key: str) -> bool:
    return club_key.lower() in FREE_AGENT_NAMES


def _ensure_column(connection: Connection, table_name: str, column_name: str, column_type: str) -> None:
    existing_columns = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name not in existing_columns:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN "{column_name}" {column_type};'))


def _update_player_utility_values(connection: Connection, players: pd.DataFrame) -> None:
    existing_columns = {column["name"] for column in inspect(connection).get_columns("players")}
    target_columns = [
        column
        for column in ("Expected_Utility_Value", "Expected_Utility")
        if column in existing_columns
    ]
    if not target_columns:
        return

    assignments = ", ".join(f'"{column}" = :expected_utility_value' for column in target_columns)
    update_query = text(
        f'''
        UPDATE players
        SET {assignments}
        WHERE "Player_ID" = :player_id
        '''
    )
    params = [
        {
            "player_id": int(row.Player_ID),
            "expected_utility_value": float(row.Expected_Utility_Value),
        }
        for row in players.itertuples(index=False)
    ]
    connection.execute(update_query, params)


def _update_country_totals(connection: Connection, totals: pd.DataFrame) -> None:
    update_query = text(
        '''
        UPDATE countries
        SET "Total_Utility_Value" = :total_utility_value
        WHERE "Name" = :country
        '''
    )
    params = [
        {
            "country": row.Country,
            "total_utility_value": float(row.Total_Utility_Value),
        }
        for row in totals.itertuples(index=False)
    ]
    connection.execute(update_query, params)


def _get_connection(db: Session | Connection | Engine) -> Connection:
    if isinstance(db, Session):
        return db.connection()
    if isinstance(db, Engine):
        return db.connect()
    return db


def _commit_if_session(db: Session | Connection | Engine) -> None:
    if isinstance(db, Session):
        db.commit()


def _default_output_path() -> Path:
    return Path(__file__).resolve().parents[1] / "value_transform.csv"


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Player_Name",
            "Country",
            "Market_Value",
            "Age_Mult",
            "Position_Mult",
            "Rank_Mult",
            "Synergy_Mult",
            "Expected_Utility_Value",
        ]
    )
