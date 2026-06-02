import time
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime

# ---------------------------------------------------------
# STEP 1: Scrape Matches from Wikipedia
# ---------------------------------------------------------
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

def scrape_matches():
    print("Fetching match schedule from Wikipedia main page...")
    url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"
    # Define a custom User-Agent headers dictionary
    headers = {
        'User-Agent': 'WorldCupDataScraper/1.0 (your_email@example.com) Python-requests/2.31.0'
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Failed to fetch Wikipedia page.")
        return pd.DataFrame()
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Target divs with class="footballbox" and the specific sports event schema
    match_boxes = soup.find_all('div', class_='footballbox', itemtype='http://schema.org/SportsEvent')
    
    matches_data = []
    
    for box in match_boxes:
        try:
            # 2. Extract Date (inside div class="fdate")
            date_tag = box.find(class_='fdate')
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                # Clean up non-breaking spaces (\xa0) and Wikipedia citation brackets
                date_text = date_text.replace('\xa0', ' ')
                date_text = re.sub(r'\[\d+\]', '', date_text)
                # Remove the hidden ISO date text in parentheses if it gets grabbed
                date_text = re.sub(r'\s*\(.*\)', '', date_text).strip()
            else:
                date_text = "TBD"
            
            # 3. Extract Team_A (fhome) and Team_B (faway)
            home_tag = box.find(class_='fhome')
            away_tag = box.find(class_='faway')
            
            team_a = home_tag.get_text(strip=True).replace('\xa0', ' ').strip() if home_tag else "TBD"
            team_b = away_tag.get_text(strip=True).replace('\xa0', ' ').strip() if away_tag else "TBD"
            
            # 4. Extract Match_ID from the th element with class="fscore"
            score_tag = box.find('th', class_='fscore')
            match_id = None
            if score_tag:
                score_text = score_tag.get_text(strip=True)
                # Use regex to grab only the digits (e.g., "Match 11" -> 11)
                match_num = re.search(r'\d+', score_text)
                if match_num:
                    match_id = int(match_num.group())
            
            # 5. Extract Stadium and City from class="fright"
            fright_tag = box.find(class_='fright')
            stadium_name = "TBD"
            city_name = "TBD"
            
            if fright_tag:
                # Find all hyperlinked texts inside the location wrapper
                links = fright_tag.find_all('a')
                if len(links) >= 1:
                    stadium_name = links[0].get_text(strip=True)
                if len(links) >= 2:
                    city_name = links[1].get_text(strip=True)
            
            # 6. Determine Match Type (Matches 1-72 are Group stage)
            match_type = "Group" if match_id and match_id <= 72 else "Knockout"
            
            if match_id is not None:
                matches_data.append({
                    "Match_ID": match_id,
                    "Date": date_text,
                    "Team_A": team_a,
                    "Team_B": team_b,
                    "Stadium_Name": stadium_name,
                    "City": city_name,
                    "Match_Type": match_type,
                    "Goals_A": None,
                    "Goals_B": None
                })
                
        except Exception as e:
            print(f"Skipping a match box due to parsing error: {e}")
            
    # Convert list to DataFrame
    df_matches = pd.DataFrame(matches_data)
    
    if df_matches.empty:
        print("\nError: No matches matches found. The Wikipedia layout format may have changed.")
        return df_matches
        
    # Sort data frame by Match_ID so Match 1 is at the top and the Final (104) is at the bottom
    df_matches = df_matches.sort_values(by="Match_ID").reset_index(drop=True)
    
    # Rearrange columns exactly to your desired schema
    columns_order = ["Match_ID", "Date", "Team_A", "Team_B", "Stadium_Name", "City", "Match_Type", "Goals_A", "Goals_B"]
    df_matches = df_matches[columns_order]
    
    print(f"\nSuccessfully scraped {len(df_matches)} matches.")
    df_matches.to_csv('world_cup_matches.csv', index=False)
    print("Saved -> world_cup_matches.csv")
    
    return df_matches

# ---------------------------------------------------------
# STEP 2: Geocode Locations (Lat, Lon, UTC Offset)
# ---------------------------------------------------------
def get_utc_offset(lat, lon):
    """Calculates exact UTC offset for a given Lat/Lon during the summer of 2026."""
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    
    if not tz_name:
        return 0
        
    # Use a date during the World Cup to ensure Daylight Saving Time is accurately captured
    tz = pytz.timezone(tz_name)
    target_date = datetime(2026, 6, 15)
    offset_seconds = tz.utcoffset(target_date).total_seconds()
    
    # Convert seconds to hours (e.g., -14400 -> -4.0)
    return int(offset_seconds / 3600)

def build_locations(df_matches, base_camps_csv="world_cup_countries.csv"):
    print("\nStarting geographic geocoding. This will take a moment (OpenStreetMap requires 1-second delays)...")
    
    geolocator = Nominatim(user_agent="world_cup_simulation_engine")
    locations_data = []
    
    # 1. Get unique stadiums from matches
    stadiums = df_matches['Stadium_Name'].unique().tolist() if not df_matches.empty else []
    
    # 2. Get unique base camps from countries CSV
    try:
        df_countries = pd.read_csv(base_camps_csv)
        base_camps = df_countries['Base_Camp_City'].dropna().unique().tolist()
    except FileNotFoundError:
        print(f"Warning: {base_camps_csv} not found. Skipping Base Camps.")
        base_camps = []

    # Compile the master list of dictionaries to look up
    lookup_queue = [{"name": s, "type": "Stadium"} for s in stadiums if s != "TBD"] + \
                   [{"name": b, "type": "Base_Camp"} for b in base_camps if str(b) != "nan"]

    for item in lookup_queue:
        loc_name = item['name']
        loc_type = item['type']
        
        try:
            # Ping OpenStreetMap
            geo = geolocator.geocode(loc_name, timeout=10)
            
            if geo:
                lat, lon = geo.latitude, geo.longitude
                utc_offset = get_utc_offset(lat, lon)
                
                locations_data.append({
                    "Location_Name": loc_name,
                    "Type": loc_type,
                    "Latitude": round(lat, 4),
                    "Longitude": round(lon, 4),
                    "UTC_Offset": utc_offset
                })
                print(f" ✓ Found: {loc_name} ({utc_offset} UTC)")
            else:
                print(f" x Could not geocode: {loc_name}")
                locations_data.append({
                    "Location_Name": loc_name,
                    "Type": loc_type,
                    "Latitude": None,
                    "Longitude": None,
                    "UTC_Offset": None
                })
                
        except GeocoderTimedOut:
            print(f" x Timeout while searching for {loc_name}")
            
        # Respect OpenStreetMap's terms of service (1 lookup per second)
        time.sleep(1.2)
        
    df_locations = pd.DataFrame(locations_data)
    
    # Remove any exact duplicates if a city is both a Base Camp and a Stadium location
    df_locations = df_locations.drop_duplicates(subset=['Location_Name', 'Type'])
    
    df_locations.to_csv('world_cup_locations.csv', index=False)
    print("\nSaved -> world_cup_locations.csv")
    
    return df_locations

# ---------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------
if __name__ == "__main__":
    matches_df = scrape_matches()
    build_locations(matches_df)
    print("\nAll data pipelines completed successfully!")