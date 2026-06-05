from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session


Stage = Literal["group", "knockout"]
ScoreMode = Literal["Prediction", "Current"]

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
        current_match = _get_match_row(connection, match_id)
        match_team_a = str(current_match["Team_A"])
        match_team_b = str(current_match["Team_B"])

        if team_a is not None and team_a != match_team_a:
            raise ValueError(f"team_a must match the match row Team_A: {match_team_a}")
        if team_b is not None and team_b != match_team_b:
            raise ValueError(f"team_b must match the match row Team_B: {match_team_b}")

        country_a = _country_lookup_name(match_team_a)
        country_b = _country_lookup_name(match_team_b)
        country_a_row = _get_country_row(connection, country_a, match_team_a)
        country_b_row = _get_country_row(connection, country_b, match_team_b)

        current_stadium = str(current_match["Stadium_Name"])
        current_location = _get_location_row(connection, current_stadium)
        previous_a = _previous_team_match_row(connection, match_id, match_team_a)
        previous_b = _previous_team_match_row(connection, match_id, match_team_b)

        rest_adjustment_a, rest_adjustment_b = _rest_adjustments(
            current_match,
            previous_a,
            previous_b,
        )

        score_a = (
            _base_strength(country_a_row)
            + _home_boost(match_team_a, current_stadium)
            + rest_adjustment_a
            + _travel_adjustment_row(
                connection,
                current_match,
                current_location,
                match_team_a,
                country_a_row,
            )
        )
        score_b = (
            _base_strength(country_b_row)
            + _home_boost(match_team_b, current_stadium)
            + rest_adjustment_b
            + _travel_adjustment_row(
                connection,
                current_match,
                current_location,
                match_team_b,
                country_b_row,
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


def calculate_all_group_score_matrices(
    db: Session | Connection | Engine,
    mode: ScoreMode,
) -> dict[str, pd.DataFrame]:
    """Calculate standings tables for every group.

    Args:
        db: SQLAlchemy Session, Connection, or Engine connected to the app database.
        mode: "Prediction" uses predicted goals. "Current" uses actual goals.

    Returns:
        A dictionary keyed by group name, with one standings DataFrame per group.
    """
    if mode not in {"Prediction", "Current"}:
        raise ValueError('mode must be either "Prediction" or "Current"')

    connection = _get_connection(db)
    should_close = isinstance(db, Engine)

    try:
        countries = pd.read_sql_query(text('SELECT * FROM countries'), connection)
        matches = pd.read_sql_query(text('SELECT * FROM matches'), connection)
        if countries.empty:
            return {}

        group_tables = _initialize_group_tables(countries)
        if matches.empty:
            return _rank_all_groups(group_tables)

        goals_a_column, goals_b_column = _score_columns_for_mode(mode)
        group_matches = matches[matches["Match_Type"] == "Group"].copy()
        for match in group_matches.itertuples(index=False):
            goals_a = getattr(match, goals_a_column)
            goals_b = getattr(match, goals_b_column)
            if _is_missing_score(goals_a) or _is_missing_score(goals_b):
                continue

            team_a = _country_lookup_name(str(match.Team_A))
            team_b = _country_lookup_name(str(match.Team_B))
            if team_a not in group_tables or team_b not in group_tables:
                continue

            _apply_group_match_result(
                group_tables,
                team_a,
                team_b,
                int(float(goals_a)),
                int(float(goals_b)),
            )

        return _rank_all_groups(group_tables)
    finally:
        if should_close:
            connection.close()


def pretty_print_group_score_matrices(group_score_matrices: dict[str, pd.DataFrame]) -> str:
    """Pretty print and return all group standings."""
    if not group_score_matrices:
        output = "No group standings available."
        print(output)
        return output

    sections = []
    display_columns = ["Rank", "Team", "Pld", "W", "D", "L", "GF", "GA", "GD", "Pts"]
    for group_name in sorted(group_score_matrices):
        table = group_score_matrices[group_name][display_columns]
        sections.append(f"Group {group_name}\n{table.to_string(index=False)}")

    output = "\n\n".join(sections)
    print(output)
    return output


def get_third_place_opponents_dict(
    db: Session | Connection | Engine,
    options_csv_path: Optional[str | Path] = None,
) -> dict[str, str]:
    """Return the knockout option row matching the predicted top third-place teams."""
    group_score_matrices = calculate_all_group_score_matrices(db, "Prediction")
    third_places = _third_place_rows(group_score_matrices)
    if len(third_places) < 8:
        raise ValueError("At least 8 third-place teams are required to select knockout opponents")

    top_third_places = set(
        "3" + str(row.Group)
        for row in third_places.head(8).itertuples(index=False)
    )

    options_path = Path(options_csv_path) if options_csv_path else _default_options_path()
    options = pd.read_csv(options_path)
    for _, option in options.iterrows():
        option_dict = option.to_dict()
        row_set = {
            str(value)
            for column_name, value in option_dict.items()
            if column_name != "Option" and not pd.isna(value)
        }
        if row_set == top_third_places:
            return _normalize_option_row(option_dict)

    raise ValueError(f"No options.csv row matched third-place set: {sorted(top_third_places)}")


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


def _get_match_row(connection: Connection, match_id: int) -> dict:
    match = connection.execute(
        text('SELECT * FROM matches WHERE "Match_ID" = :match_id'),
        {"match_id": int(match_id)},
    ).mappings().first()
    if match is None:
        raise ValueError(f"match not found: {match_id}")
    return dict(match)


def _get_country_row(connection: Connection, country_name: str, display_name: str) -> dict:
    country = connection.execute(
        text('SELECT * FROM countries WHERE "Name" = :country_name'),
        {"country_name": country_name},
    ).mappings().first()
    if country is None:
        raise ValueError(f"country not found: {display_name}")
    return dict(country)


def _get_location(locations: pd.DataFrame, location_name: str) -> pd.Series:
    if location_name not in locations.index:
        raise ValueError(f"location not found: {location_name}")
    return locations.loc[location_name]


def _get_location_row(connection: Connection, location_name: str) -> dict:
    location = connection.execute(
        text('SELECT * FROM locations WHERE "Location_Name" = :location_name'),
        {"location_name": location_name},
    ).mappings().first()
    if location is None:
        raise ValueError(f"location not found: {location_name}")
    return dict(location)


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


def _previous_team_match_row(connection: Connection, match_id: int, team: str) -> Optional[dict]:
    previous_match = connection.execute(
        text(
            '''
            SELECT *
            FROM matches
            WHERE "Match_ID" < :match_id
              AND ("Team_A" = :team OR "Team_B" = :team)
            ORDER BY "Match_ID" DESC
            LIMIT 1
            '''
        ),
        {"match_id": int(match_id), "team": team},
    ).mappings().first()
    return dict(previous_match) if previous_match is not None else None


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


def _previous_knockout_match_row(connection: Connection, match_id: int, team: str) -> Optional[dict]:
    previous_match = connection.execute(
        text(
            '''
            SELECT *
            FROM matches
            WHERE "Match_ID" < :match_id
              AND "Match_Type" = 'Knockout'
              AND ("Team_A" = :team OR "Team_B" = :team)
            ORDER BY "Match_ID" DESC
            LIMIT 1
            '''
        ),
        {"match_id": int(match_id), "team": team},
    ).mappings().first()
    return dict(previous_match) if previous_match is not None else None


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


def _travel_adjustment_row(
    connection: Connection,
    current_match: dict,
    current_location: dict,
    schedule_team: str,
    country: dict,
) -> float:
    source_location = _travel_source_location_row(
        connection,
        current_match,
        schedule_team,
        country,
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


def _travel_source_location_row(
    connection: Connection,
    current_match: dict,
    schedule_team: str,
    country: dict,
) -> dict:
    match_type = str(current_match["Match_Type"])
    match_id = int(current_match["Match_ID"])

    if match_type == "Knockout":
        previous_knockout = _previous_knockout_match_row(connection, match_id, schedule_team)
        if previous_knockout is not None:
            return _get_location_row(connection, str(previous_knockout["Stadium_Name"]))

    return _get_location_row(connection, str(country["Base_Camp_City"]))


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


def _initialize_group_tables(countries: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tables = {}
    countries = countries.sort_values(["Group", "Name"])
    for country in countries.itertuples(index=False):
        group_name = str(country.Group)
        team_name = str(country.Name)
        base_elo = pd.to_numeric(getattr(country, "Base_Elo", 0.0), errors="coerce")
        base_elo = 0.0 if pd.isna(base_elo) else float(base_elo)
        row = {
            "Group": group_name,
            "Team": team_name,
            "Base_Elo": base_elo,
            "Rank": 0,
            "Pld": 0,
            "W": 0,
            "D": 0,
            "L": 0,
            "GF": 0,
            "GA": 0,
            "GD": 0,
            "Pts": 0,
        }
        if team_name not in tables:
            tables[team_name] = row

    return tables


def _score_columns_for_mode(mode: ScoreMode) -> tuple[str, str]:
    if mode == "Prediction":
        return "Predicted_Goals_A", "Predicted_Goals_B"
    return "Goals_A", "Goals_B"


def _apply_group_match_result(
    team_rows: dict[str, dict[str, object]],
    team_a: str,
    team_b: str,
    goals_a: int,
    goals_b: int,
) -> None:
    row_a = team_rows[team_a]
    row_b = team_rows[team_b]

    row_a["Pld"] += 1
    row_b["Pld"] += 1
    row_a["GF"] += goals_a
    row_a["GA"] += goals_b
    row_b["GF"] += goals_b
    row_b["GA"] += goals_a
    row_a["GD"] = row_a["GF"] - row_a["GA"]
    row_b["GD"] = row_b["GF"] - row_b["GA"]

    if goals_a > goals_b:
        row_a["W"] += 1
        row_b["L"] += 1
        row_a["Pts"] += 3
    elif goals_b > goals_a:
        row_b["W"] += 1
        row_a["L"] += 1
        row_b["Pts"] += 3
    else:
        row_a["D"] += 1
        row_b["D"] += 1
        row_a["Pts"] += 1
        row_b["Pts"] += 1


def _rank_all_groups(team_rows: dict[str, dict[str, object]]) -> dict[str, pd.DataFrame]:
    standings = pd.DataFrame(team_rows.values())
    if standings.empty:
        return {}

    grouped_tables = {}
    for group_name, group_table in standings.groupby("Group", sort=True):
        ranked_table = group_table.sort_values(
            ["Pts", "GD", "GF", "Base_Elo", "Team"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)
        ranked_table["Rank"] = ranked_table.index + 1
        grouped_tables[str(group_name)] = ranked_table[
            ["Rank", "Team", "Pld", "W", "D", "L", "GF", "GA", "GD", "Pts", "Base_Elo"]
        ]

    return grouped_tables


def _third_place_rows(group_score_matrices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for group_name, group_table in group_score_matrices.items():
        third_place = group_table[group_table["Rank"] == 3]
        if third_place.empty:
            continue

        row = third_place.iloc[0].copy()
        row["Group"] = group_name
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["Group", "Team", "Pts", "GD", "GF"])

    third_places = pd.DataFrame(rows)
    return third_places.sort_values(
        ["Pts", "GD", "GF", "Group"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)


def _normalize_option_row(option_dict: dict[str, object]) -> dict[str, object]:
    normalized = {}
    for column_name, value in option_dict.items():
        if column_name == "Option":
            normalized[column_name] = int(value) if not pd.isna(value) else value
        else:
            normalized[str(column_name)] = str(value)
    return normalized


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


def _is_missing_score(value: object) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip() == ""


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


def _default_options_path() -> Path:
    return Path(__file__).resolve().parents[1] / "options.csv"


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
