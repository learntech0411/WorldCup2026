from pydantic import BaseModel
from typing import Optional

# -----------------------------------------
# LOCATION SCHEMAS
# -----------------------------------------
class LocationBase(BaseModel):
    Location_Name: str
    Type: str  # 'Stadium' or 'Base_Camp'
    Country: Optional[str] = None
    Latitude: Optional[float] = None
    Longitude: Optional[float] = None
    UTC_Offset: Optional[int] = None

class Location(LocationBase):
    class Config:
        from_attributes = True

# -----------------------------------------
# COUNTRY SCHEMAS
# -----------------------------------------
class CountryBase(BaseModel):
    Name: str
    Base_Elo: float
    Base_Camp_City: str
    Total_Utility_Value: float
    Synergies: str
    Injured_Players: str = ""

class Country(CountryBase):
    class Config:
        from_attributes = True

# -----------------------------------------
# PLAYER SCHEMAS
# -----------------------------------------
class PlayerBase(BaseModel):
    Name: str
    Country: str
    Age: Optional[int] = None
    Player_Number: Optional[str] = None
    Raw_Position: str
    Model_Position: str # 'Attacker', 'Midfielder', 'Defender', 'Goalkeeper'
    Club: str
    Market_Value: float
    Expected_Utility: Optional[float] = None
    Is_Injured: bool = False

class Player(PlayerBase):
    Player_ID: int # This comes from the database auto-increment

    class Config:
        from_attributes = True

# -----------------------------------------
# MATCH SCHEMAS
# -----------------------------------------
class MatchBase(BaseModel):
    Match_ID: int
    Date: str
    Team_A: str
    Team_B: str
    Stadium_Name: str
    Match_Type: str # 'Group' or 'Knockout'
    
    # Actual Results (Nullable until the match happens)
    Goals_A: Optional[int] = None
    Goals_B: Optional[int] = None
    Actual_Winner: Optional[str] = None
    
    # Model Predictions (Nullable until predicted)
    Predicted_Goals_A: Optional[float] = None
    Predicted_Goals_B: Optional[float] = None
    Predicted_Winner: Optional[str] = None
    Winning_Probability_A: Optional[float] = None
    Winning_Probability_B: Optional[float] = None
    Draw_Probability: Optional[float] = None

class Match(MatchBase):
    class Config:
        from_attributes = True
