import time
import re
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
import unicodedata

# --- HELPER FUNCTIONS ---

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

            all_players.append(player_dict)

    print("Closing browser...")
    driver.quit()

    # 4. Save to CSV using pandas
    df = pd.DataFrame(all_players)
    
    # Reorder columns to match your exact specification
    columns_order = [
        'Name', 'Country', 'Age', 'Player_Number', 
        'Raw_Position', 'Model_Position', 'Club', 
        'Market_Value', 'Is_Injured'
    ]
    df = df[columns_order]
    
    df.to_csv('world_cup_players.csv', index=False, encoding='utf-8')
    print("Success! Data saved to 'world_cup_players.csv'")


def clean_string(text):
    """Removes accents, normalizes apostrophes, and strips hidden whitespace characters."""
    if not text:
        return ""
    # Normalize unicode (e.g., Côte d'Ivoire -> Cote d'Ivoire)
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    # Standardize all variations of curly apostrophes/quotes to a normal straight single quote
    text = text.replace("’", "'").replace("`", "'").replace("‘", "'")
    # Clean hidden space bytes
    text = text.replace('\xa0', ' ').replace('\u200b', ' ')
    return text.strip()

def scrape_countries_data():
    print("Starting Firefox...")
    options = Options()
    # options.add_argument('--headless') # Uncomment to run invisibly
    driver = webdriver.Firefox(options=options)
    
    # ---------------------------------------------------------
    # STEP 1: Scrape FIFA Base Camps
    # ---------------------------------------------------------
    print("Fetching FIFA Base Camps...")
    fifa_url = "https://inside.fifa.com/organisation/media-releases/world-cup-2026-team-base-camps-tbc-48-nations-usa-mexico-canada"
    driver.get(fifa_url)
    time.sleep(4) # Wait for page to load
    
    soup_fifa = BeautifulSoup(driver.page_source, 'html.parser')
    base_camps = {}
    
    # Iterate through all table rows
    for row in soup_fifa.find_all('tr'):
        tds = row.find_all('td')
        if len(tds) >= 2:
            # Clean up hidden characters, non-breaking spaces, and trim
            country = tds[0].get_text(strip=True).replace('\xa0', '').replace('\u200b', '')
            city = tds[1].get_text(strip=True).replace('\xa0', '').replace('\u200b', '')
            
            # Skip header rows or empties
            if country and city and country != "Participating Member Association":
                base_camps[country] = city
                
    print(f"Found {len(base_camps)} Base Camps from FIFA.")

    # ---------------------------------------------------------
    # STEP 2: Scrape Elo Ratings
    # ---------------------------------------------------------
    print("Fetching Elo Ratings...")
    elo_url = "https://www.eloratings.net/2026"
    driver.get(elo_url)
    time.sleep(3) # Wait for initial Javascript to render the grid
    
    # SlickGrid virtualizes rows. Scroll the inner viewport down to render all teams.
    try:
        viewport = driver.find_element(By.CSS_SELECTOR, ".slick-viewport")
        for _ in range(15):
            driver.execute_script("arguments[0].scrollTop += 600;", viewport)
            time.sleep(0.2)
    except Exception as e:
        print("Could not scroll viewport, some lower ranked teams might be missed.")

    soup_elo = BeautifulSoup(driver.page_source, 'html.parser')
    elo_ratings = {}
    
    # Find all rendered grid rows
    for row in soup_elo.find_all('div', class_='slick-row'):
        team_cell = row.find('div', class_='team-cell')
        rating_cell = row.find('div', class_='l2') # Rating is stored in column l2
        
        if team_cell and rating_cell:
            a_tag = team_cell.find('a')
            if a_tag and 'href' in a_tag.attrs:
                team_href = a_tag['href'].strip() 
                rating = rating_cell.get_text(strip=True)
                try:
                    elo_ratings[team_href] = int(rating)
                except ValueError:
                    pass
                    
    print(f"Found {len(elo_ratings)} total Elo Ratings in the table.")
    driver.quit()

    # ---------------------------------------------------------
    # STEP 3: Map Names and Filter 48 Participating Teams
    # ---------------------------------------------------------
    # The dictionary now expects the straight apostrophe version and maps to the Elo key
    name_mapping = {
        "Algeria": "Algeria", "Argentina": "Argentina", "Australia": "Australia", 
        "Austria": "Austria", "Belgium": "Belgium", "Bosnia and Herzegovina": "Bosnia_and_Herzegovina", 
        "Brazil": "Brazil", "Cabo Verde": "Cape_Verde", "Canada": "Canada", 
        "Colombia": "Colombia", "Congo DR": "DR_Congo", "Cote d'Ivoire": "Ivory_Coast", 
        "Côte d'Ivoire": "Ivory_Coast", "Croatia": "Croatia", "Curaçao": "Curacao", 
        "Czechia": "Czechia", "Ecuador": "Ecuador", "Egypt": "Egypt", "England": "England", 
        "France": "France", "Germany": "Germany", "Ghana": "Ghana", 
        "Haiti": "Haiti", "IR Iran": "Iran", "Iraq": "Iraq", 
        "Japan": "Japan", "Jordan": "Jordan", "Korea Republic": "South_Korea", 
        "Mexico": "Mexico", "Morocco": "Morocco", "Netherlands": "Netherlands", 
        "New Zealand": "New_Zealand", "Norway": "Norway", "Panama": "Panama", 
        "Paraguay": "Paraguay", "Portugal": "Portugal", "Qatar": "Qatar", 
        "Saudi Arabia": "Saudi_Arabia", "Scotland": "Scotland", "Senegal": "Senegal", 
        "South Africa": "South_Africa", "Spain": "Spain", "Sweden": "Sweden", 
        "Switzerland": "Switzerland", "Tunisia": "Tunisia", "Türkiye": "Turkey", 
        "United States": "United_States", "Uruguay": "Uruguay", "Uzbekistan": "Uzbekistan"
    }

    final_data = []
    
    for fifa_name, city in base_camps.items():
        # Standardize the string: convert curly quotes to straight quotes
        clean_fifa_name = fifa_name.replace("’", "'").replace("‘", "'")
        
        elo_lookup_key = name_mapping.get(clean_fifa_name)
        
        if not elo_lookup_key:
            print(f"Warning: '{clean_fifa_name}' is not in our 48-team mapping dictionary!")
            continue
            
        if elo_lookup_key in elo_ratings:
            # FORMAT OVERRIDE: Use the Elo name instead of the FIFA name
            # By replacing the underscore with a space, "South_Korea" becomes "South Korea"
            elo_display_name = elo_lookup_key.replace("_", " ")
            
            final_data.append({
                "Name": elo_display_name,
                "Base_Elo": elo_ratings[elo_lookup_key],
                "Base_Camp_City": city
            })
        else:
            print(f"Warning: Could not find Elo rating for mapped key: {elo_lookup_key}")

    # ---------------------------------------------------------
    # STEP 4: Save to CSV
    # ---------------------------------------------------------
    df = pd.DataFrame(final_data)
    
    # Sort alphabetically by the new clean Elo names
    df = df.sort_values(by="Name").reset_index(drop=True)
    
    print(f"\nSuccessfully compiled {len(df)} of the 48 participating countries.")
    
    df.to_csv('world_cup_countries.csv', index=False, encoding='utf-8')
    print("Data saved to 'world_cup_countries.csv'")

if __name__ == "__main__":
    # scrape_world_cup_players()
    scrape_countries_data()