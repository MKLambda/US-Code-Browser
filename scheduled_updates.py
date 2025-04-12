import requests
from bs4 import BeautifulSoup
import re
import logging
import json
from pathlib import Path
import time
from datetime import datetime
import sys
import os

# Import our modules
from download_usc_releases import USCReleaseDownloader, find_all_release_points
from usc_processor import USCProcessor
from verify_titles import verify_titles

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger('scheduled_updates')

def get_current_release_point():
    """Get the current release point from the website"""
    try:
        response = requests.get("https://uscode.house.gov/download/download.shtml")
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the current release point information
        release_info = soup.find(string=re.compile(r'Public Law \d+-\d+ \(\d+/\d+/\d+\)'))
        if release_info:
            match = re.search(r'Public Law (\d+-\d+) \((\d+/\d+/\d+)\)', release_info)
            if match:
                return {
                    'public_law': match.group(1),
                    'date': match.group(2)
                }
        
        return None
    except Exception as e:
        logger.error(f"Error getting current release point: {e}")
        return None

def load_last_update_info():
    """Load information about the last update"""
    info_file = Path("update_info.json")
    if info_file.exists():
        try:
            with open(info_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading update info: {e}")
    
    return {
        'last_update': None,
        'last_public_law': None,
        'processed_titles': []
    }

def save_update_info(info):
    """Save information about the current update"""
    info_file = Path("update_info.json")
    try:
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
        logger.info("Update info saved")
    except Exception as e:
        logger.error(f"Error saving update info: {e}")

def check_and_update():
    """Check for updates and process new releases if available"""
    logger.info("Checking for updates...")
    
    # Get the current release point
    current_release = get_current_release_point()
    if not current_release:
        logger.error("Failed to get current release point")
        return False
    
    logger.info(f"Current release: Public Law {current_release['public_law']} ({current_release['date']})")
    
    # Load information about the last update
    update_info = load_last_update_info()
    
    # Check if this is a new release
    if update_info['last_public_law'] == current_release['public_law']:
        logger.info("No new releases available")
        return False
    
    logger.info(f"New release available: {update_info['last_public_law']} -> {current_release['public_law']}")
    
    # Find all release points
    all_releases = find_all_release_points()
    if not all_releases:
        logger.error("Failed to find release points")
        return False
    
    # Initialize downloader and processor
    download_dir = Path("downloads")
    output_dir = Path("processed")
    download_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    downloader = USCReleaseDownloader(download_dir=str(download_dir))
    processor = USCProcessor(download_dir=str(download_dir), output_dir=str(output_dir))
    
    # Process each title
    processed_titles = []
    for title_num in sorted(all_releases.keys()):
        if title_num == 53:  # Skip title 53 as it's reserved
            continue
            
        try:
            # Get the latest release for this title
            latest_release = all_releases[title_num][0]
            release_info = latest_release['release']
            url = latest_release['url']
            
            # Format title number with leading zeros
            title_str = str(title_num).zfill(2)
            
            # Construct the output filename
            output_filename = f"title{title_str}_{release_info}.zip"
            output_path = download_dir / output_filename
            
            # Download the file
            logger.info(f"Downloading Title {title_str} (Release {release_info})...")
            success = downloader.download_from_direct_url(url, output_filename)
            if not success:
                logger.error(f"Failed to download Title {title_str}")
                continue
            
            # Process the file
            logger.info(f"Processing Title {title_str}...")
            processor.process_zip_file(output_path)
            
            processed_titles.append(title_num)
            
            # Add a small delay between titles
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing Title {title_num}: {e}")
    
    # Verify the processed titles
    title_numbers, missing_titles, invalid_files = verify_titles()
    
    # Update the update info
    update_info['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_info['last_public_law'] = current_release['public_law']
    update_info['processed_titles'] = processed_titles
    
    # Save the update info
    save_update_info(update_info)
    
    logger.info(f"Update completed: {len(processed_titles)} titles processed")
    
    if missing_titles:
        logger.warning(f"Missing titles: {missing_titles}")
    
    if invalid_files:
        logger.warning(f"Invalid files: {invalid_files}")
    
    return True

def setup_scheduled_task():
    """Set up a scheduled task to run this script every 30 days"""
    if sys.platform == 'win32':
        # Windows
        task_name = "USCUpdateTask"
        script_path = os.path.abspath(__file__)
        python_exe = sys.executable
        
        # Create a batch file to run the script
        batch_file = Path("run_update.bat")
        with open(batch_file, 'w') as f:
            f.write(f'@echo off\n"{python_exe}" "{script_path}" --run\n')
        
        # Create the scheduled task
        cmd = f'schtasks /create /tn {task_name} /tr "{batch_file}" /sc DAILY /mo 30 /st 03:00 /ru SYSTEM /f'
        
        logger.info(f"Setting up scheduled task with command: {cmd}")
        os.system(cmd)
        
        logger.info(f"Scheduled task '{task_name}' created to run every 30 days at 3:00 AM")
    
    elif sys.platform.startswith('linux') or sys.platform == 'darwin':
        # Linux or macOS
        script_path = os.path.abspath(__file__)
        python_exe = sys.executable
        
        # Create a crontab entry
        cron_cmd = f'0 3 */30 * * {python_exe} {script_path} --run'
        
        logger.info(f"To set up a cron job, run the following command:")
        logger.info(f"(crontab -l 2>/dev/null; echo '{cron_cmd}') | crontab -")
    
    else:
        logger.error(f"Unsupported platform: {sys.platform}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Check for and download USC updates')
    parser.add_argument('--run', action='store_true', help='Run the update check')
    parser.add_argument('--setup', action='store_true', help='Set up a scheduled task')
    
    args = parser.parse_args()
    
    if args.run:
        check_and_update()
    elif args.setup:
        setup_scheduled_task()
    else:
        parser.print_help()
