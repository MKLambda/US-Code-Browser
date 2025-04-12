"""
Enhanced US Code Updates

This script provides an enhanced update system for the US Code, including:
- Robust error handling and recovery
- Detailed change tracking
- Email notifications
- Backup and restore functionality
"""

import logging
import json
import time
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# Import our modules
from download_usc_releases import USCReleaseDownloader, find_all_release_points
from usc_processor import USCProcessor
from verify_titles import verify_titles
from update_tracker import USCodeUpdateTracker

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'enhanced_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger('enhanced_updates')

class EnhancedUpdater:
    """Enhanced US Code updater with robust error handling and recovery"""
    
    def __init__(self, config_file="enhanced_updates_config.json"):
        """Initialize the enhanced updater
        
        Args:
            config_file (str): Path to configuration file
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        # Initialize directories
        self.download_dir = Path(self.config['directories']['downloads'])
        self.processed_dir = Path(self.config['directories']['processed'])
        self.backup_dir = Path(self.config['directories']['backups'])
        
        self.download_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.tracker = USCodeUpdateTracker(data_dir=self.config['directories']['update_data'])
        self.downloader = USCReleaseDownloader(download_dir=str(self.download_dir))
        self.processor = USCProcessor(
            download_dir=str(self.download_dir), 
            output_dir=str(self.processed_dir)
        )
    
    def _load_config(self):
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Default configuration
        default_config = {
            "directories": {
                "downloads": "downloads",
                "processed": "processed",
                "backups": "backups",
                "update_data": "update_data"
            },
            "update": {
                "retry_attempts": 3,
                "retry_delay_seconds": 300,
                "backup_before_update": True,
                "notify_on_update": True,
                "validate_downloads": True
            },
            "notifications": {
                "send_email": True,
                "notify_on_error": True
            }
        }
        
        # Save default configuration
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def create_backup(self):
        """Create a backup of the processed data
        
        Returns:
            str: Backup directory path or None if failed
        """
        if not self.processed_dir.exists():
            logger.warning("No processed data to backup")
            return None
        
        try:
            # Create a timestamped backup directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup_{timestamp}"
            backup_path.mkdir(exist_ok=True)
            
            # Copy all processed files
            for file in self.processed_dir.glob("*.json"):
                shutil.copy2(file, backup_path)
            
            logger.info(f"Backup created at {backup_path}")
            return str(backup_path)
        
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
    def restore_from_backup(self, backup_path=None):
        """Restore data from a backup
        
        Args:
            backup_path (str): Path to backup directory, or None for latest
            
        Returns:
            bool: True if restore was successful
        """
        try:
            # If no backup path provided, use the latest
            if backup_path is None:
                backup_dirs = list(self.backup_dir.glob("backup_*"))
                if not backup_dirs:
                    logger.error("No backups found")
                    return False
                
                # Sort by name (which includes timestamp)
                backup_dirs.sort(reverse=True)
                backup_path = backup_dirs[0]
            else:
                backup_path = Path(backup_path)
            
            if not backup_path.exists():
                logger.error(f"Backup path does not exist: {backup_path}")
                return False
            
            # Clear the processed directory
            for file in self.processed_dir.glob("*.json"):
                file.unlink()
            
            # Copy files from backup
            for file in backup_path.glob("*.json"):
                shutil.copy2(file, self.processed_dir)
            
            logger.info(f"Restored from backup: {backup_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False
    
    def validate_download(self, file_path):
        """Validate a downloaded file
        
        Args:
            file_path (str): Path to the downloaded file
            
        Returns:
            bool: True if file is valid
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # Check file size
        if file_path.stat().st_size < 1000:  # Arbitrary minimum size
            logger.error(f"File too small: {file_path}")
            return False
        
        # For ZIP files, we could add more validation here
        # such as checking if it's a valid ZIP archive
        
        return True
    
    def download_with_retry(self, url, output_filename, max_attempts=None):
        """Download a file with retry logic
        
        Args:
            url (str): URL to download
            output_filename (str): Output filename
            max_attempts (int): Maximum number of attempts, or None for config default
            
        Returns:
            bool: True if download was successful
        """
        if max_attempts is None:
            max_attempts = self.config['update']['retry_attempts']
        
        retry_delay = self.config['update']['retry_delay_seconds']
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"Download attempt {attempt}/{max_attempts}: {url}")
            
            success = self.downloader.download_from_direct_url(url, output_filename)
            
            if success:
                output_path = self.download_dir / output_filename
                
                # Validate the download if enabled
                if self.config['update']['validate_downloads']:
                    if not self.validate_download(output_path):
                        logger.error(f"Downloaded file failed validation: {output_path}")
                        if attempt < max_attempts:
                            logger.info(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            continue
                        return False
                
                logger.info(f"Download successful: {output_filename}")
                return True
            
            if attempt < max_attempts:
                logger.info(f"Download failed, retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Download failed after {max_attempts} attempts: {url}")
                return False
        
        return False
    
    def process_title(self, title_num, release_info):
        """Process a specific title
        
        Args:
            title_num (int): Title number
            release_info (dict): Release information
            
        Returns:
            bool: True if processing was successful
        """
        try:
            # Format title number with leading zeros
            title_str = str(title_num).zfill(2)
            
            # Get release details
            release_version = release_info['release']
            url = release_info['url']
            
            # Construct the output filename
            output_filename = f"title{title_str}_{release_version}.zip"
            output_path = self.download_dir / output_filename
            
            # Download the file with retry
            success = self.download_with_retry(url, output_filename)
            if not success:
                return False
            
            # Process the file
            logger.info(f"Processing Title {title_str}...")
            self.processor.process_zip_file(output_path)
            
            logger.info(f"Title {title_str} processed successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error processing Title {title_num}: {e}")
            return False
    
    def run_update(self):
        """Run the update process
        
        Returns:
            bool: True if update was successful
        """
        logger.info("Starting enhanced update process...")
        
        # Check for updates
        is_new, current_release, previous_release = self.tracker.is_new_release_available()
        
        if not is_new:
            logger.info("No new updates available")
            return True
        
        logger.info(f"New release available: {previous_release['public_law']} -> {current_release['public_law']}")
        
        # Create backup if enabled
        if self.config['update']['backup_before_update']:
            backup_path = self.create_backup()
            if not backup_path:
                logger.warning("Failed to create backup, continuing anyway")
        
        # Find all release points
        all_releases = find_all_release_points()
        if not all_releases:
            logger.error("Failed to find release points")
            return False
        
        # Process each title
        processed_titles = []
        failed_titles = []
        
        for title_num in sorted(all_releases.keys()):
            if title_num == 53:  # Skip title 53 as it's reserved
                continue
            
            # Get the latest release for this title
            latest_release = all_releases[title_num][0]
            
            # Process the title
            success = self.process_title(title_num, latest_release)
            
            if success:
                processed_titles.append(title_num)
            else:
                failed_titles.append(title_num)
            
            # Add a small delay between titles
            time.sleep(1)
        
        # Verify the processed titles
        title_numbers, missing_titles, invalid_files = verify_titles()
        
        # Generate changelog
        changelog = self.tracker.generate_changelog(current_release, previous_release)
        
        # Save the current release info
        self.tracker.save_release_info(current_release)
        
        # Send notifications if enabled
        if self.config['update']['notify_on_update'] and changelog:
            notification_count = self.tracker.send_update_notification(changelog)
            logger.info(f"Sent {notification_count} update notifications")
        
        # Log results
        logger.info(f"Update completed: {len(processed_titles)} titles processed, {len(failed_titles)} failed")
        
        if failed_titles:
            logger.warning(f"Failed titles: {failed_titles}")
        
        if missing_titles:
            logger.warning(f"Missing titles: {missing_titles}")
        
        if invalid_files:
            logger.warning(f"Invalid files: {invalid_files}")
        
        return len(failed_titles) == 0
    
    def setup_scheduled_task(self):
        """Set up a scheduled task to run updates
        
        Returns:
            bool: True if setup was successful
        """
        try:
            if sys.platform == 'win32':
                # Windows
                task_name = "USCEnhancedUpdateTask"
                script_path = os.path.abspath(__file__)
                python_exe = sys.executable
                
                # Create a batch file to run the script
                batch_file = Path("run_enhanced_update.bat")
                with open(batch_file, 'w') as f:
                    f.write(f'@echo off\n"{python_exe}" "{script_path}" --run\n')
                
                # Create the scheduled task
                cmd = f'schtasks /create /tn {task_name} /tr "{batch_file}" /sc DAILY /mo 30 /st 03:00 /ru SYSTEM /f'
                
                logger.info(f"Setting up scheduled task with command: {cmd}")
                os.system(cmd)
                
                logger.info(f"Scheduled task '{task_name}' created to run every 30 days at 3:00 AM")
                return True
            
            elif sys.platform.startswith('linux') or sys.platform == 'darwin':
                # Linux or macOS
                script_path = os.path.abspath(__file__)
                python_exe = sys.executable
                
                # Create a crontab entry
                cron_cmd = f'0 3 */30 * * {python_exe} {script_path} --run'
                
                logger.info(f"To set up a cron job, run the following command:")
                logger.info(f"(crontab -l 2>/dev/null; echo '{cron_cmd}') | crontab -")
                
                # We can't automatically set up cron jobs, so just provide instructions
                return True
            
            else:
                logger.error(f"Unsupported platform: {sys.platform}")
                return False
        
        except Exception as e:
            logger.error(f"Error setting up scheduled task: {e}")
            return False

# Command-line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced US Code Updates')
    parser.add_argument('--run', action='store_true', help='Run the update process')
    parser.add_argument('--setup', action='store_true', help='Set up a scheduled task')
    parser.add_argument('--backup', action='store_true', help='Create a backup of processed data')
    parser.add_argument('--restore', metavar='PATH', nargs='?', const=None, help='Restore from a backup (latest if no path provided)')
    parser.add_argument('--check', action='store_true', help='Check for updates without downloading')
    parser.add_argument('--config', action='store_true', help='Edit configuration')
    
    args = parser.parse_args()
    
    updater = EnhancedUpdater()
    
    if args.run:
        updater.run_update()
    
    elif args.setup:
        updater.setup_scheduled_task()
    
    elif args.backup:
        backup_path = updater.create_backup()
        if backup_path:
            print(f"Backup created at: {backup_path}")
        else:
            print("Backup failed")
    
    elif args.restore is not None:
        success = updater.restore_from_backup(args.restore)
        if success:
            print("Restore completed successfully")
        else:
            print("Restore failed")
    
    elif args.check:
        tracker = updater.tracker
        is_new, current, previous = tracker.is_new_release_available()
        
        if is_new:
            print(f"New release available: {previous['public_law']} -> {current['public_law']}")
            print(f"Current release date: {current['date']}")
        else:
            print("No new updates available")
            if current:
                print(f"Current release: Public Law {current['public_law']} ({current['date']})")
    
    elif args.config:
        # Simple configuration editor
        print("Editing configuration:")
        
        # Update directories
        print("\nDirectories:")
        for key, value in updater.config['directories'].items():
            new_value = input(f"{key} [{value}]: ").strip()
            if new_value:
                updater.config['directories'][key] = new_value
        
        # Update settings
        print("\nUpdate settings:")
        for key, value in updater.config['update'].items():
            if isinstance(value, bool):
                new_value = input(f"{key} [{value}] (y/n): ").strip().lower()
                if new_value:
                    updater.config['update'][key] = new_value == 'y'
            else:
                new_value = input(f"{key} [{value}]: ").strip()
                if new_value:
                    try:
                        # Convert to int if the original value was an int
                        if isinstance(value, int):
                            updater.config['update'][key] = int(new_value)
                        else:
                            updater.config['update'][key] = new_value
                    except ValueError:
                        print(f"Invalid value for {key}, keeping original")
        
        # Update notification settings
        print("\nNotification settings:")
        for key, value in updater.config['notifications'].items():
            if isinstance(value, bool):
                new_value = input(f"{key} [{value}] (y/n): ").strip().lower()
                if new_value:
                    updater.config['notifications'][key] = new_value == 'y'
            else:
                new_value = input(f"{key} [{value}]: ").strip()
                if new_value:
                    updater.config['notifications'][key] = new_value
        
        # Save configuration
        updater.save_config()
        print("Configuration saved")
    
    else:
        parser.print_help()
