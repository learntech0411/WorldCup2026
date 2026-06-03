import time
import re
import requests
import pandas as pd
import unicodedata
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from timezonefinder import TimezoneFinder
import pytz
from datetime import datetime

def map_model_position(raw_position):
    """Maps Transfermarkt specific positions to our 4 Model Positions"""
    raw = raw_position.strip().lower()
    
    if 'goalkeeper' in raw:
        return 'Goalkeeper'
    elif 'back' in raw or 'defender' in raw:
        return 'Defender'
    elif 'midfield' in raw:
        return 'Midfielder'
    elif 'winger' in raw or 'striker' in raw or 'forward' in raw or 'attack' in raw:
        return 'Attacker'
    else:
        return 'Unknown'

def parse_market_value(mv_string):
    """Converts strings like '€20.00m' or '€800k' to a float in millions (e.g. 20.0, 0.8)"""
    mv_string = mv_string.replace('€', '').strip()
    if not mv_string or mv_string == '-':
        return 0.0
        
    if 'm' in mv_string:
        return float(mv_string.replace('m', ''))
    elif 'k' in mv_string:
        return float(mv_string.replace('k', '')) / 1000
    return 0.0

# --- MAIN SCRAPER ---

def scrape_world_cup_players():
    print("Starting Firefox...")
    
    # Set up Firefox options
    options = Options()
    # options.add_argument('--headless') # Uncomment this if you want it to run invisibly in the background
    
    # Initialize the Firefox driver
    driver = webdriver.Firefox(options=options)
    
    base_url = "https://www.transfermarkt.com"
    start_url = f"{base_url}/world-cup/teilnehmer/pokalwettbewerb/FIWC"
    
    print(f"Loading main tournament page: {start_url}")
    driver.get(start_url)
    time.sleep(3) # Wait for Cloudflare/Page to load
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # 1. Get all participating countries and their links
    countries_data = []
    main_table = soup.find('table', class_='items')
    
    if not main_table:
        print("Error: Could not find the main countries table. Transfermarkt might be blocking the request.")
        driver.quit()
        return

    for row in main_table.find('tbody').find_all('tr'):
        link_tag = row.find('td', class_='hauptlink').find('a')
        if link_tag:
            country_name = link_tag.get_text(strip=True)
            country_url = base_url + link_tag['href']
            countries_data.append({'name': country_name, 'url': country_url})

    print(f"Found {len(countries_data)} countries. Beginning player extraction...")
    
    all_players = []

    # 2. Loop through each country's URL
    for country in countries_data:
        print(f"Scraping players for {country['name']}...")
        driver.get(country['url'])
        
        # BE POLITE: Transfermarkt will IP ban you if you scrape too fast. 
        # A 3-5 second delay between page loads is highly recommended.
        time.sleep(4) 
        
        country_soup = BeautifulSoup(driver.page_source, 'html.parser')
        players_table = country_soup.find('table', class_='items')
        
        if not players_table:
            print(f"  -> Skipping {country['name']}: Could not find players table.")
            continue
            
        # 3. Extract player rows
        for row in players_table.find('tbody').find_all('tr', recursive=False):
            player_dict = {}
            
            # --- Country ---
            player_dict['Country'] = country['name']
            
            # --- Player Number ---
            num_div = row.find('div', class_='rn_nummer')
            player_dict['Player_Number'] = num_div.get_text(strip=True) if num_div else "-"
            
            # --- Name & Injury Status ---
            # Transfermarkt nests the name inside an inline-table
            hauptlink_td = row.find('td', class_='hauptlink')
            if hauptlink_td:
                a_tag = hauptlink_td.find('a')
                if a_tag:
                    # Using list(stripped_strings)[0] to avoid capturing the hidden text of the injury span
                    player_dict['Name'] = list(a_tag.stripped_strings)[0]
                    
                    # Check for injury span
                    injury_span = a_tag.find('span', class_='verletzt-table')
                    player_dict['Is_Injured'] = True if injury_span else False
                else:
                    continue # Skip if no name found
            else:
                continue
                
            # --- Positions ---
            # Raw position is usually in the second row of the inline-table under the name
            inline_table = row.find('table', class_='inline-table')
            if inline_table:
                trs = inline_table.find_all('tr')
                if len(trs) > 1:
                    raw_pos = trs[1].find('td').get_text(strip=True)
                    player_dict['Raw_Position'] = raw_pos
                    player_dict['Model_Position'] = map_model_position(raw_pos)
            
            # --- Age ---
            # Format: 21/08/2002 (23) -> We use regex to grab the number in parentheses
            age_td = row.find_all('td', class_='zentriert')[1] # Usually the second centered td
            age_text = age_td.get_text(strip=True)
            age_match = re.search(r'\((\d+)\)', age_text)
            player_dict['Age'] = int(age_match.group(1)) if age_match else None
            
            # --- Club ---
            club_img = row.find('img', class_='') # Usually the club crest
            if club_img and 'title' in club_img.attrs:
                player_dict['Club'] = club_img['title']
            else:
                player_dict['Club'] = "Free Agent"
                
            # --- Market Value ---
            mv_td = row.find('td', class_='rechts hauptlink')
            if mv_td and mv_td.find('a'):
                mv_raw = mv_td.find('a').get_text(strip=True)
                player_dict['Market_Value'] = parse_market_value(mv_raw)
            else:
                player_dict['Market_Value'] = 0.0

            # Expected Utility Value
            player_dict['Expected_Utility'] = None

            all_players.append(player_dict)

    print("Closing browser...")
    driver.quit()

    # 4. Save to CSV using pandas
    df = pd.DataFrame(all_players)
    
    # Reorder columns to match your exact specification
    columns_order = [
        'Name', 'Country', 'Age', 'Player_Number', 
        'Raw_Position', 'Model_Position', 'Club', 
        'Market_Value', 'Expected_Utility', 'Is_Injured'
    ]
    df = df[columns_order]
    
    df.to_csv('world_cup_players.csv', index=False, encoding='utf-8')
    print("Success! Data saved to 'world_cup_players.csv'")

def clean_string(text):
    """Removes accents, normalizes apostrophes, and strips hidden whitespace characters."""
    if not text:
        return ""
        
    # FIX: We must replace curly apostrophes BEFORE forcing the text into ASCII!
    text = text.replace("’", "'").replace("`", "'").replace("‘", "'")
    
    # Normalize unicode (e.g., Côte d'Ivoire -> Cote d'Ivoire)
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    
    # Clean hidden space bytes
    text = text.replace('\xa0', ' ').replace('\u200b', ' ')
    
    return text.strip()

def scrape_countries_data():
    # ---------------------------------------------------------
    # STEP 1: Scrape FIFA Base Camps (Using Requests - Fast)
    # ---------------------------------------------------------
    print("Fetching FIFA Base Camps...")
    fifa_url = "https://inside.fifa.com/organisation/media-releases/world-cup-2026-team-base-camps-tbc-48-nations-usa-mexico-canada"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(fifa_url, headers=headers)
    soup_fifa = BeautifulSoup(response.text, 'html.parser')
    
    base_camps = {}
    
    # Iterate through all table rows
    for row in soup_fifa.find_all('tr'):
        tds = row.find_all('td')
        if len(tds) >= 2:
            raw_country = tds[0].get_text()
            country = clean_string(raw_country)
            city = tds[1].get_text(strip=True).replace('\xa0', ' ').replace('\u200b', '').strip()
            
            if country and city and country != "Participating Member Association":
                base_camps[country] = city
                
    print(f"Found {len(base_camps)} Base Camps from FIFA.")

    # ---------------------------------------------------------
    # STEP 2: Scrape Elo Ratings (Using Selenium - Required for JS)
    # ---------------------------------------------------------
    print("Starting Firefox to fetch Elo Ratings...")
    options = Options()
    # options.add_argument('--headless') # Uncomment to run invisibly
    driver = webdriver.Firefox(options=options)
    
    elo_url = "https://www.eloratings.net/2026"
    driver.get(elo_url)
    time.sleep(4) # Wait for Javascript to render the grid
    
    # Scroll to load the virtualized grid
    try:
        viewport = driver.find_element(By.CSS_SELECTOR, ".slick-viewport")
        for _ in range(15):
            driver.execute_script("arguments[0].scrollTop += 600;", viewport)
            time.sleep(0.2)
    except Exception as e:
        print("Could not scroll viewport. Check if the page loaded correctly.")

    soup_elo = BeautifulSoup(driver.page_source, 'html.parser')
    elo_ratings = {}
    
    for row in soup_elo.find_all('div', class_='slick-row'):
        import re
        team_cell = row.find('div', class_=re.compile(r'team-cell'))
        rating_cell = row.find('div', class_='l2') # Column l2 holds the rating
        
        if team_cell and rating_cell:
            a_tag = team_cell.find('a')
            if a_tag and 'href' in a_tag.attrs:
                team_href = a_tag['href'].strip() 
                rating_text = rating_cell.get_text(strip=True)
                try:
                    elo_ratings[team_href] = int(rating_text)
                except ValueError:
                    pass
                    
    print(f"Found {len(elo_ratings)} total Elo Ratings.")

    # ---------------------------------------------------------
    # STEP 3: Scrape Groups from Wikipedia (Using Selenium)
    # ---------------------------------------------------------
    print("Fetching Group assignments from Wikipedia...")
    wiki_url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_draw"
    driver.get(wiki_url)
    time.sleep(2) # Brief wait for page load
    
    soup_wiki = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Wikipedia names sometimes differ from your existing Elo keys
    wiki_to_elo = {
        "Algeria": "Algeria", "Argentina": "Argentina", "Australia": "Australia", 
        "Austria": "Austria", "Belgium": "Belgium", "Bosnia and Herzegovina": "Bosnia_and_Herzegovina", 
        "Brazil": "Brazil", "Cape Verde": "Cape_Verde", "Canada": "Canada", 
        "Colombia": "Colombia", "DR Congo": "DR_Congo", "Ivory Coast": "Ivory_Coast", 
        "Croatia": "Croatia", "Curaçao": "Curacao", "Czech Republic": "Czechia", 
        "Ecuador": "Ecuador", "Egypt": "Egypt", "England": "England", 
        "France": "France", "Germany": "Germany", "Ghana": "Ghana", 
        "Haiti": "Haiti", "Iran": "Iran", "Iraq": "Iraq", 
        "Japan": "Japan", "Jordan": "Jordan", "South Korea": "South_Korea", 
        "Mexico": "Mexico", "Morocco": "Morocco", "Netherlands": "Netherlands", 
        "New Zealand": "New_Zealand", "Norway": "Norway", "Panama": "Panama", 
        "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Qatar", 
        "Saudi Arabia": "Saudi_Arabia", "Scotland": "Scotland", "Senegal": "Senegal", 
        "South Africa": "South_Africa", "Spain": "Spain", "Sweden": "Sweden", 
        "Switzerland": "Switzerland", "Tunisia": "Tunisia", "Turkey": "Turkey", 
        "United States": "United_States", "Uruguay": "Uruguay", "Uzbekistan": "Uzbekistan"
    }
    
    elo_to_group = {}
    
    # Locate all tables containing the group data
    for table in soup_wiki.find_all('table', class_='wikitable col1center'):
        caption = table.find('caption')
        if not caption:
            continue
            
        group_text = caption.get_text(strip=True)
        if "Group" in group_text:
            # Extract just the letter (e.g., "Group A" -> "A")
            group_letter = group_text.replace("Group", "").strip()
            
            # Skip the header row and iterate over team rows
            for row in table.find_all('tr')[1:]:
                tds = row.find_all('td')
                if len(tds) >= 2:
                    team_link = tds[1].find('a')
                    if team_link:
                        team_name = team_link.get_text(strip=True)
                        # Map Wikipedia name to your Elo key
                        elo_key = wiki_to_elo.get(team_name, team_name.replace(" ", "_"))
                        elo_to_group[elo_key] = group_letter
                        
    print(f"Found {len(elo_to_group)} group assignments.")
    driver.quit()

    # ---------------------------------------------------------
    # STEP 4: Map Names and Filter 48 Participating Teams
    # ---------------------------------------------------------
    name_mapping = {
        "Algeria": "Algeria", "Argentina": "Argentina", "Australia": "Australia", 
        "Austria": "Austria", "Belgium": "Belgium", "Bosnia and Herzegovina": "Bosnia_and_Herzegovina", 
        "Brazil": "Brazil", "Cabo Verde": "Cape_Verde", "Canada": "Canada", 
        "Colombia": "Colombia", "Congo DR": "DR_Congo", "Cote d'Ivoire": "Ivory_Coast", 
        "Croatia": "Croatia", "Curacao": "Curacao", "Czechia": "Czechia", 
        "Ecuador": "Ecuador", "Egypt": "Egypt", "England": "England", 
        "France": "France", "Germany": "Germany", "Ghana": "Ghana", 
        "Haiti": "Haiti", "IR Iran": "Iran", "Iraq": "Iraq", 
        "Japan": "Japan", "Jordan": "Jordan", "Korea Republic": "South_Korea", 
        "Mexico": "Mexico", "Morocco": "Morocco", "Netherlands": "Netherlands", 
        "New Zealand": "New_Zealand", "Norway": "Norway", "Panama": "Panama", 
        "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Qatar", 
        "Saudi Arabia": "Saudi_Arabia", "Scotland": "Scotland", "Senegal": "Senegal", 
        "South Africa": "South_Africa", "Spain": "Spain", "Sweden": "Sweden", 
        "Switzerland": "Switzerland", "Tunisia": "Tunisia", "Turkiye": "Turkey", 
        "United States": "United_States", "Uruguay": "Uruguay", "Uzbekistan": "Uzbekistan"
    }

    final_data = []
    
    for fifa_name, city in base_camps.items():
        elo_lookup_key = name_mapping.get(fifa_name)
        
        if not elo_lookup_key:
            print(f"Warning: '{fifa_name}' is not in our mapping dictionary!")
            continue
            
        if elo_lookup_key in elo_ratings:
            # FORMAT OVERRIDE: Use the Elo name instead of the FIFA name
            elo_display_name = elo_lookup_key.replace("_", " ")
            
            final_data.append({
                "Name": elo_display_name,
                "Group": elo_to_group.get(elo_lookup_key, "Unknown"),
                "Base_Elo": elo_ratings[elo_lookup_key],
                "Base_Camp_City": city,
                "Total_Utility_Value": 0.0,
                "Base_Strength": 0.0,
            })
        else:
            print(f"Warning: Could not find Elo rating for mapped key: {elo_lookup_key}")

    # ---------------------------------------------------------
    # STEP 5: Save to CSV
    # ---------------------------------------------------------
    df = pd.DataFrame(final_data)
    
    if df.empty:
        print("\nError: DataFrame is empty. Something went wrong with the mapping.")
        return
        
    df = df.sort_values(by=["Group", "Name"]).reset_index(drop=True)
    
    print(f"\nSuccessfully compiled {len(df)} of the 48 participating countries.")
    
    df.to_csv('world_cup_countries.csv', index=False, encoding='utf-8')
    print("Data saved to 'world_cup_countries.csv'")

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
    
    # --- HELPER FUNCTION FOR TEAM NAMES ---
    def format_team_name(team_name):
        if team_name.startswith("Runner-up Group "):
            return team_name.replace("Runner-up Group ", "2", 1)
        elif team_name.startswith("Winner Group "):
            return team_name.replace("Winner Group ", "1", 1)
        elif team_name.startswith("Winner Match "):
            return team_name.replace("Winner Match ", "W", 1)
        elif team_name.startswith("Loser Match "):
            return team_name.replace("Loser Match ", "L", 1)
        return team_name
    # --------------------------------------
    
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
            
            team_a_raw = home_tag.get_text(strip=True).replace('\xa0', ' ').strip() if home_tag else "TBD"
            team_b_raw = away_tag.get_text(strip=True).replace('\xa0', ' ').strip() if away_tag else "TBD"
            
            # Apply formatting to convert generic placeholders into coded slots (e.g., "1A", "W73")
            team_a = format_team_name(team_a_raw)
            team_b = format_team_name(team_b_raw)
            
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
                    "Goals_B": None,
                    "Predicted_Goals_A": None,
                    "Predicted_Goals_B": None,
                    "Winning_Probability_A": None,
                    "Winning_Probability_B": None,
                    "Draw_Probability": None,
                })
                
        except Exception as e:
            print(f"Skipping a match box due to parsing error: {e}")
            
    # Convert list to DataFrame
    df_matches = pd.DataFrame(matches_data)
    
    if df_matches.empty:
        print("\nError: No matches found. The Wikipedia layout format may have changed.")
        return df_matches
        
    # Sort data frame by Match_ID so Match 1 is at the top and the Final (104) is at the bottom
    df_matches = df_matches.sort_values(by="Match_ID").reset_index(drop=True)
    
    # Rearrange columns exactly to your desired schema
    columns_order = ["Match_ID", "Date", "Team_A", "Team_B", "Stadium_Name", "City", "Match_Type", "Goals_A", "Goals_B", "Predicted_Goals_A", "Predicted_Goals_B", "Winning_Probability_A", "Winning_Probability_B", "Draw_Probability"]
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

if __name__ == "__main__":
    scrape_world_cup_players()
    scrape_countries_data()
    matches_df = scrape_matches()
    build_locations(matches_df)
    print("\nAll data collections completed!")