import time
import requests
import pandas as pd
import unicodedata
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By

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
                "Group": elo_to_group.get(elo_lookup_key, "Unknown"), # <-- Added Group mapping
                "Base_Elo": elo_ratings[elo_lookup_key],
                "Base_Camp_City": city,
                "Total_Utility_Value": 0.0
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

if __name__ == "__main__":
    scrape_countries_data()