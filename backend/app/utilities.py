from math import asin, cos, radians, sin, sqrt
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
COUNTRY_NAME_ALIASES = {
    "Czech Republic": "Czechia",
    "Curaçao": "Curacao",
}
HOME_COUNTRY_STADIUMS = {
    "Mexico": {"Estadio Azteca", "Estadio Akron", "Estadio BBVA"},
    "Canada": {"BMO Field", "BC Place", "Toronto Stadium"},
    "United States": {
        "SoFi Stadium",
        "Gillette Stadium",
        "MetLife Stadium",
        "Levi's Stadium",
        "Lincoln Financial Field",
        "NRG Stadium",
        "AT&T Stadium",
        "Hard Rock Stadium",
        "Mercedes-Benz Stadium",
        "Lumen Field",
        "Arrowhead Stadium",
    },
}
HOME_BOOST_ELO = 100.0
REST_ELO_PER_DAY = 15.0
TIMEZONE_ELO_PENALTY = 5.0
DISTANCE_ELO_PENALTY_PER_500_KM = 1.0
EARTH_RADIUS_KM = 6371.0


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


def calculate_base_strengths(db: Session | Connection | Engine) -> pd.DataFrame:
    """Calculate and store each country's blended base strength.

    Utility values are min-max scaled onto the tournament's Elo range, then merged
    with Base_Elo using: Base_Strength = 0.6 * Base_Elo + 0.4 * Utility_Elo.
    """
    connection = _get_connection(db)
    transaction = connection.begin() if isinstance(db, Engine) else None
    should_close = isinstance(db, Engine)

    try:
        _ensure_column(connection, "countries", "Total_Utility_Value", "FLOAT DEFAULT 0")
        _ensure_column(connection, "countries", "Base_Strength", "FLOAT DEFAULT 0")

        countries = pd.read_sql_query(text('SELECT * FROM countries'), connection)
        if countries.empty:
            if transaction is not None:
                transaction.commit()
            _commit_if_session(db)
            return _empty_base_strength_result()

        countries["Base_Elo"] = pd.to_numeric(countries["Base_Elo"], errors="coerce").fillna(0.0)
        countries["Total_Utility_Value"] = pd.to_numeric(
            countries["Total_Utility_Value"],
            errors="coerce",
        ).fillna(0.0)

        min_utility = countries["Total_Utility_Value"].min()
        max_utility = countries["Total_Utility_Value"].max()
        min_elo = countries["Base_Elo"].min()
        max_elo = countries["Base_Elo"].max()

        if max_utility == min_utility:
            countries["Utility_Ratio"] = 0.0
        else:
            countries["Utility_Ratio"] = (
                (countries["Total_Utility_Value"] - min_utility)
                / (max_utility - min_utility)
            )

        countries["Utility_Elo"] = min_elo + countries["Utility_Ratio"] * (max_elo - min_elo)
        countries["Base_Strength"] = 0.6 * countries["Base_Elo"] + 0.4 * countries["Utility_Elo"]

        result = countries[
            [
                "Name",
                "Base_Elo",
                "Total_Utility_Value",
                "Utility_Elo",
                "Base_Strength",
            ]
        ].sort_values("Base_Strength", ascending=False)

        _update_country_base_strengths(connection, result)
        if transaction is not None:
            transaction.commit()
        _commit_if_session(db)

        return result
    except Exception:
        if transaction is not None:
            transaction.rollback()
        raise
    finally:
        if should_close:
            connection.close()


def calculate_match_power_score(
    db: Session | Connection | Engine,
    match_id: int,
    team_a: Optional[str] = None,
    team_b: Optional[str] = None,
) -> dict[str, float]:
    """Calculate match power scores for both teams in a match."""
    connection = _get_connection(db)
    should_close = isinstance(db, Engine)

    try:
        countries = pd.read_sql_query(text('SELECT * FROM countries'), connection)
        matches = pd.read_sql_query(text('SELECT * FROM matches'), connection)
        locations = pd.read_sql_query(text('SELECT * FROM locations'), connection)

        if countries.empty:
            raise ValueError("countries table is empty")
        if matches.empty:
            raise ValueError("matches table is empty")
        if locations.empty:
            raise ValueError("locations table is empty")

        current_match = _get_match(matches, match_id)
        match_team_a = str(current_match["Team_A"])
        match_team_b = str(current_match["Team_B"])

        if team_a is not None and team_a != match_team_a:
            raise ValueError(f"team_a must match the match row Team_A: {match_team_a}")
        if team_b is not None and team_b != match_team_b:
            raise ValueError(f"team_b must match the match row Team_B: {match_team_b}")

        countries = countries.set_index("Name", drop=False)
        locations = locations.set_index("Location_Name", drop=False)
        country_a = _country_lookup_name(match_team_a)
        country_b = _country_lookup_name(match_team_b)
        if country_a not in countries.index:
            raise ValueError(f"country not found: {match_team_a}")
        if country_b not in countries.index:
            raise ValueError(f"country not found: {match_team_b}")

        current_stadium = str(current_match["Stadium_Name"])
        current_location = _get_location(locations, current_stadium)
        previous_a = _previous_team_match(matches, match_id, match_team_a)
        previous_b = _previous_team_match(matches, match_id, match_team_b)

        rest_adjustment_a, rest_adjustment_b = _rest_adjustments(
            current_match,
            previous_a,
            previous_b,
        )

        score_a = (
            _base_strength(countries.loc[country_a])
            + _home_boost(match_team_a, current_stadium)
            + rest_adjustment_a
            + _travel_adjustment(
                countries,
                locations,
                matches,
                current_match,
                current_location,
                match_team_a,
                country_a,
            )
        )
        score_b = (
            _base_strength(countries.loc[country_b])
            + _home_boost(match_team_b, current_stadium)
            + rest_adjustment_b
            + _travel_adjustment(
                countries,
                locations,
                matches,
                current_match,
                current_location,
                match_team_b,
                country_b,
            )
        )

        return {
            "Match_ID": int(match_id),
            "Team_A": match_team_a,
            "Team_B": match_team_b,
            "Match_Power_Score_A": float(score_a),
            "Match_Power_Score_B": float(score_b),
        }
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


def _get_match(matches: pd.DataFrame, match_id: int) -> pd.Series:
    match_rows = matches[pd.to_numeric(matches["Match_ID"], errors="coerce") == match_id]
    if match_rows.empty:
        raise ValueError(f"match not found: {match_id}")
    return match_rows.iloc[0]


def _get_location(locations: pd.DataFrame, location_name: str) -> pd.Series:
    if location_name not in locations.index:
        raise ValueError(f"location not found: {location_name}")
    return locations.loc[location_name]


def _country_lookup_name(country_name: str) -> str:
    return COUNTRY_NAME_ALIASES.get(country_name, country_name)


def _base_strength(country: pd.Series) -> float:
    base_strength = pd.to_numeric(country.get("Base_Strength"), errors="coerce")
    if pd.isna(base_strength) or float(base_strength) == 0.0:
        base_elo = pd.to_numeric(country.get("Base_Elo"), errors="coerce")
        return 0.0 if pd.isna(base_elo) else float(base_elo)
    return float(base_strength)


def _home_boost(team: str, stadium_name: str) -> float:
    if stadium_name in HOME_COUNTRY_STADIUMS.get(team, set()):
        return HOME_BOOST_ELO
    return 0.0


def _previous_team_match(matches: pd.DataFrame, match_id: int, team: str) -> Optional[pd.Series]:
    match_ids = pd.to_numeric(matches["Match_ID"], errors="coerce")
    previous_matches = matches[
        (match_ids < match_id)
        & ((matches["Team_A"] == team) | (matches["Team_B"] == team))
    ].copy()
    if previous_matches.empty:
        return None
    previous_matches["Match_ID_Numeric"] = pd.to_numeric(previous_matches["Match_ID"], errors="coerce")
    previous_matches = previous_matches.sort_values("Match_ID_Numeric", ascending=False)
    return previous_matches.iloc[0]


def _previous_knockout_match(matches: pd.DataFrame, match_id: int, team: str) -> Optional[pd.Series]:
    match_ids = pd.to_numeric(matches["Match_ID"], errors="coerce")
    previous_matches = matches[
        (match_ids < match_id)
        & (matches["Match_Type"] == "Knockout")
        & ((matches["Team_A"] == team) | (matches["Team_B"] == team))
    ].copy()
    if previous_matches.empty:
        return None
    previous_matches["Match_ID_Numeric"] = pd.to_numeric(previous_matches["Match_ID"], errors="coerce")
    previous_matches = previous_matches.sort_values("Match_ID_Numeric", ascending=False)
    return previous_matches.iloc[0]


def _rest_adjustments(
    current_match: pd.Series,
    previous_a: Optional[pd.Series],
    previous_b: Optional[pd.Series],
) -> tuple[float, float]:
    rest_a = _rest_days(current_match, previous_a)
    rest_b = _rest_days(current_match, previous_b)

    if rest_a is None and rest_b is None:
        rest_differential = 0.0
    elif rest_a is None:
        rest_differential = rest_b or 0.0
    elif rest_b is None:
        rest_differential = -rest_a
    else:
        rest_differential = rest_a - rest_b

    adjustment_a = rest_differential * REST_ELO_PER_DAY
    return adjustment_a, -adjustment_a


def _rest_days(current_match: pd.Series, previous_match: Optional[pd.Series]) -> Optional[float]:
    if previous_match is None:
        return None

    current_date = pd.to_datetime(current_match["Date"])
    previous_date = pd.to_datetime(previous_match["Date"])
    return float((current_date - previous_date).days)


def _travel_adjustment(
    countries: pd.DataFrame,
    locations: pd.DataFrame,
    matches: pd.DataFrame,
    current_match: pd.Series,
    current_location: pd.Series,
    schedule_team: str,
    country_name: str,
) -> float:
    source_location = _travel_source_location(
        countries,
        locations,
        matches,
        current_match,
        schedule_team,
        country_name,
    )
    distance_km = _haversine_km(
        source_location["Latitude"],
        source_location["Longitude"],
        current_location["Latitude"],
        current_location["Longitude"],
    )
    timezone_crossings = abs(float(current_location["UTC_Offset"]) - float(source_location["UTC_Offset"]))
    return -(
        timezone_crossings * TIMEZONE_ELO_PENALTY
        + (distance_km / 500.0) * DISTANCE_ELO_PENALTY_PER_500_KM
    )


def _travel_source_location(
    countries: pd.DataFrame,
    locations: pd.DataFrame,
    matches: pd.DataFrame,
    current_match: pd.Series,
    schedule_team: str,
    country_name: str,
) -> pd.Series:
    match_type = str(current_match["Match_Type"])
    match_id = int(current_match["Match_ID"])

    if match_type == "Knockout":
        previous_knockout = _previous_knockout_match(matches, match_id, schedule_team)
        if previous_knockout is not None:
            return _get_location(locations, str(previous_knockout["Stadium_Name"]))

    base_camp_city = str(countries.loc[country_name]["Base_Camp_City"])
    return _get_location(locations, base_camp_city)


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


def _update_country_base_strengths(connection: Connection, countries: pd.DataFrame) -> None:
    update_query = text(
        '''
        UPDATE countries
        SET "Base_Strength" = :base_strength
        WHERE "Name" = :country
        '''
    )
    params = [
        {
            "country": row.Name,
            "base_strength": float(row.Base_Strength),
        }
        for row in countries.itertuples(index=False)
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


def _empty_base_strength_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Name",
            "Base_Elo",
            "Total_Utility_Value",
            "Utility_Elo",
            "Base_Strength",
        ]
    )
