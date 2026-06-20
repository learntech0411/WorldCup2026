from pathlib import Path
import sys
import tempfile

import pandas as pd
from sqlalchemy import create_engine, text


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.predictions import winner_prediction  # noqa: E402
from app.utilities import (  # noqa: E402
    calculate_all_group_score_matrices,
    calculate_base_strengths,
    calculate_total_utility_values,
)


def test_player_expected_utility_uses_age_position_and_rank_multipliers():
    engine = create_engine("sqlite:///:memory:")
    seed_countries(engine, [{"Name": "Testland", "Base_Elo": 1800}])
    seed_players(
        engine,
        [
            player(1, "Prime Defender", age=25, position="Defender", market_value=100),
            player(2, "Young Attacker", age=20, position="Attacker", market_value=90),
            player(3, "Veteran Keeper", age=31, position="Goalkeeper", market_value=40),
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        calculate_total_utility_values(engine, output_csv_path=Path(tmpdir) / "values.csv")

    players = pd.read_sql_query(text('SELECT * FROM players'), engine).set_index("Name")

    # Prime Defender: 100 * age 1.00 * defender 1.25 * rank 1.00 * synergy 1.00
    assert players.loc["Prime Defender", "Expected_Utility_Value"] == 125.0

    # Young Attacker: 90 * age 0.70 * attacker 0.85 * rank 1.00 * synergy 1.00
    assert round(players.loc["Young Attacker", "Expected_Utility_Value"], 3) == 53.55

    # Veteran Keeper: 40 * age 1.15 * keeper 1.50 * top keeper rank 1.00 * synergy 1.00
    assert players.loc["Veteran Keeper", "Expected_Utility_Value"] == 69.0


def test_country_total_utility_is_sum_of_player_expected_utility_values():
    engine = create_engine("sqlite:///:memory:")
    seed_countries(engine, [{"Name": "Testland", "Base_Elo": 1800}])
    seed_players(
        engine,
        [
            player(1, "Prime Defender", age=25, position="Defender", market_value=100),
            player(2, "Young Attacker", age=20, position="Attacker", market_value=90),
            player(3, "Veteran Keeper", age=31, position="Goalkeeper", market_value=40),
        ],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        calculate_total_utility_values(engine, output_csv_path=Path(tmpdir) / "values.csv")

    country = pd.read_sql_query(text('SELECT * FROM countries'), engine).iloc[0]

    assert round(country["Total_Utility_Value"], 3) == 247.55


def test_base_strength_blends_base_elo_with_utility_scaled_to_elo_range():
    engine = create_engine("sqlite:///:memory:")
    seed_countries(
        engine,
        [
            {"Name": "High Elo Low Utility", "Base_Elo": 2000, "Total_Utility_Value": 10},
            {"Name": "Low Elo High Utility", "Base_Elo": 1000, "Total_Utility_Value": 30},
        ],
    )

    result = calculate_base_strengths(engine).set_index("Name")

    # Utility_Elo is scaled onto the tournament Elo range: low utility -> 1000, high utility -> 2000.
    assert result.loc["High Elo Low Utility", "Utility_Elo"] == 1000
    assert result.loc["Low Elo High Utility", "Utility_Elo"] == 2000

    # Base_Strength = 0.6 * Base_Elo + 0.4 * Utility_Elo.
    assert result.loc["High Elo Low Utility", "Base_Strength"] == 1600
    assert result.loc["Low Elo High Utility", "Base_Strength"] == 1400


def test_winner_prediction_updates_match_with_probabilities_and_predicted_score():
    engine = create_engine("sqlite:///:memory:")
    pd.DataFrame(
        [
            {
                "Match_ID": 1,
                "Date": "June 11, 2026",
                "Team_A": "Stronger",
                "Team_B": "Weaker",
                "Stadium_Name": "Test Stadium",
                "Match_Type": "Group",
                "Goals_A": None,
                "Goals_B": None,
                "Predicted_Goals_A": None,
                "Predicted_Goals_B": None,
                "Winning_Probability_A": None,
                "Winning_Probability_B": None,
                "Draw_Probability": None,
            }
        ]
    ).to_sql("matches", engine, index=False)

    prediction = winner_prediction(engine, 1, match_power_score_a=1900, match_power_score_b=1500)
    match = pd.read_sql_query(text('SELECT * FROM matches WHERE "Match_ID" = 1'), engine).iloc[0]

    assert prediction["Expected_Goals_A"] > prediction["Expected_Goals_B"]
    assert float(match["Winning_Probability_A"]) > float(match["Winning_Probability_B"])
    assert match["Predicted_Goals_A"] is not None
    assert match["Predicted_Goals_B"] is not None

    probability_sum = (
        float(match["Winning_Probability_A"])
        + float(match["Winning_Probability_B"])
        + float(match["Draw_Probability"])
    )
    assert round(probability_sum, 6) == 1.0


def test_prediction_group_matrix_uses_actual_score_before_predicted_score():
    engine = create_engine("sqlite:///:memory:")
    seed_countries(
        engine,
        [
            {"Name": "Actual Winner", "Group": "A", "Base_Elo": 1700},
            {"Name": "Predicted Winner", "Group": "A", "Base_Elo": 1800},
        ],
    )
    pd.DataFrame(
        [
            {
                "Match_ID": 1,
                "Team_A": "Actual Winner",
                "Team_B": "Predicted Winner",
                "Match_Type": "Group",
                "Goals_A": 2,
                "Goals_B": 0,
                "Predicted_Goals_A": 0,
                "Predicted_Goals_B": 3,
            }
        ]
    ).to_sql("matches", engine, index=False)

    table = calculate_all_group_score_matrices(engine, "Prediction")["A"].set_index("Team")

    assert table.loc["Actual Winner", "Pts"] == 3
    assert table.loc["Actual Winner", "GF"] == 2
    assert table.loc["Predicted Winner", "Pts"] == 0


def seed_countries(engine, countries):
    rows = []
    for country in countries:
        rows.append(
            {
                "Name": country["Name"],
                "Group": country.get("Group", "A"),
                "Base_Elo": country["Base_Elo"],
                "Base_Camp_City": country.get("Base_Camp_City", "Test Camp"),
                "Total_Utility_Value": country.get("Total_Utility_Value", 0.0),
                "Base_Strength": country.get("Base_Strength", 0.0),
            }
        )
    pd.DataFrame(rows).to_sql("countries", engine, index=False)


def seed_players(engine, players):
    pd.DataFrame(players).to_sql("players", engine, index=False)


def player(player_id, name, *, age, position, market_value, injured=False):
    return {
        "Player_ID": player_id,
        "Name": name,
        "Country": "Testland",
        "Age": age,
        "Player_Number": str(player_id),
        "Raw_Position": position,
        "Model_Position": position,
        "Club": f"Club {player_id}",
        "Market_Value": market_value,
        "Expected_Utility": None,
        "Is_Injured": injured,
    }


def run_all_tests():
    tests = [
        value
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    run_all_tests()
