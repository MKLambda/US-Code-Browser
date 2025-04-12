from pathlib import Path
import json
import re

def verify_titles():
    """Verify that all titles have been processed"""
    processed_dir = Path("processed")
    
    # Get all JSON files in the processed directory
    json_files = list(processed_dir.glob("*.json"))
    
    # Extract title numbers from filenames
    title_numbers = []
    for json_file in json_files:
        match = re.search(r'usc(\d+)\.json', json_file.name)
        if match:
            title_numbers.append(int(match.group(1)))
    
    # Sort title numbers
    title_numbers.sort()
    
    # Check which titles are missing
    missing_titles = []
    for i in range(1, 55):
        if i != 53 and i not in title_numbers:  # Skip title 53 as it's reserved
            missing_titles.append(i)
    
    # Print results
    print(f"Found {len(title_numbers)} processed titles")
    print(f"Missing titles: {missing_titles}")
    
    # Verify content of each JSON file
    invalid_files = []
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if the file has the expected structure
            if not isinstance(data, dict) or 'metadata' not in data or 'content' not in data:
                invalid_files.append(json_file.name)
                continue
            
            # Check if metadata has title information
            if 'title' not in data['metadata']:
                invalid_files.append(json_file.name)
                continue
            
            # Check if content has title information
            if 'title' not in data['content'] or not isinstance(data['content']['title'], dict):
                invalid_files.append(json_file.name)
                continue
            
        except Exception as e:
            print(f"Error verifying {json_file.name}: {e}")
            invalid_files.append(json_file.name)
    
    if invalid_files:
        print(f"Found {len(invalid_files)} invalid JSON files:")
        for file in invalid_files:
            print(f"  - {file}")
    else:
        print("All JSON files have valid structure")
    
    return title_numbers, missing_titles, invalid_files

if __name__ == "__main__":
    verify_titles()
