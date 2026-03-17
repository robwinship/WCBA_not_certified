#!/usr/bin/env python3
"""
Scraper for OBA Coach Certification Status
Fetches coaches with outstanding certifications and filters by local associations
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys

# Target cities/locals (case-insensitive)
TARGET_LOCALS = {
    'alvinston',
    'blenheim',
    'chatham',
    'corunna',
    'dresden',
    'dutton',
    'lambton shores',
    'port lambton',
    'sarnia',
    'wallaceburg',
    'wyoming'
}

def scrape_coaches():
    """Scrape the OBA webpage and extract coach data"""
    url = "https://www.registeroba.ca/certification-inprogress-by-local"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching webpage: {e}", file=sys.stderr)
        return None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all tables
    tables = soup.find_all('table')
    
    coaches_data = {}
    
    if not tables:
        print("No tables found on page", file=sys.stderr)
        return None
    
    # Process main data table (usually first or second table)
    for table in tables:
        rows = table.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            
            if len(cells) >= 4:
                local = cells[0].get_text(strip=True).lower()
                coach_name = cells[1].get_text(strip=True)
                position = cells[2].get_text(strip=True)
                reg_id = cells[3].get_text(strip=True)
                
                # Check if local is in our target list
                if local in TARGET_LOCALS:
                    # Normalize the local name for display
                    display_local = next(
                        (t for t in TARGET_LOCALS if t == local),
                        local
                    )
                    
                    if display_local not in coaches_data:
                        coaches_data[display_local] = []
                    
                    coaches_data[display_local].append({
                        'name': coach_name,
                        'position': position,
                        'reg_id': reg_id
                    })
    
    return coaches_data

def save_data(coaches_data):
    """Save coach data to JSON file"""
    if not coaches_data:
        print("No data to save", file=sys.stderr)
        return False
    
    output_data = {
        'last_updated': datetime.now().isoformat(),
        'updates_at': '8:00 AM Eastern',
        'locals': {}
    }
    
    # Sort locals and coaches by name
    for local in sorted(coaches_data.keys()):
        sorted_coaches = sorted(
            coaches_data[local],
            key=lambda x: x['name'].lower()
        )
        output_data['locals'][local.title()] = {
            'count': len(sorted_coaches),
            'coaches': sorted_coaches
        }
    
    try:
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Data saved to data.json")
        print(f"Total coaches found: {sum(d['count'] for d in output_data['locals'].values())}")
        return True
    except IOError as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        return False

if __name__ == '__main__':
    print("Starting OBA Coach Certification Scraper...")
    coaches = scrape_coaches()
    
    if coaches:
        if save_data(coaches):
            print("Scrape completed successfully!")
            sys.exit(0)
        else:
            print("Failed to save data", file=sys.stderr)
            sys.exit(1)
    else:
        print("Failed to scrape data", file=sys.stderr)
        sys.exit(1)
