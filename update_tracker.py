"""
US Code Update Tracker

This module provides enhanced tracking of US Code updates, including:
- Detailed change tracking between versions
- Email notifications for updates
- Changelog generation
"""

import json
import logging
import os
import re
import smtplib
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'update_tracker_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger('update_tracker')

class USCodeUpdateTracker:
    """Tracks updates to the US Code and provides notification capabilities"""
    
    def __init__(self, data_dir="update_data"):
        """Initialize the update tracker
        
        Args:
            data_dir (str): Directory to store update data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.versions_dir = self.data_dir / "versions"
        self.changes_dir = self.data_dir / "changes"
        self.subscribers_dir = self.data_dir / "subscribers"
        
        self.versions_dir.mkdir(exist_ok=True)
        self.changes_dir.mkdir(exist_ok=True)
        self.subscribers_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from config file"""
        config_file = self.data_dir / "config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        
        # Default configuration
        default_config = {
            "email_notifications": {
                "enabled": False,
                "smtp_server": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_address": ""
            },
            "update_check": {
                "frequency_days": 30,
                "retry_attempts": 3,
                "retry_delay_seconds": 300
            },
            "changelog": {
                "max_entries": 100,
                "include_details": True
            }
        }
        
        # Save default configuration
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def save_config(self):
        """Save configuration to config file"""
        config_file = self.data_dir / "config.json"
        
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get_current_release_info(self):
        """Get the current release information from the US Code website
        
        Returns:
            dict: Release information or None if not found
        """
        try:
            response = requests.get("https://uscode.house.gov/download/download.shtml")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for the current release point information
            release_info = soup.find(string=re.compile(r'Public Law \d+-\d+ \(\d+/\d+/\d+\)'))
            if release_info:
                match = re.search(r'Public Law (\d+-\d+) \((\d+/\d+/\d+)\)', release_info)
                if match:
                    # Parse the date
                    date_str = match.group(2)
                    date_parts = date_str.split('/')
                    if len(date_parts) == 3:
                        month, day, year = date_parts
                        formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:
                        formatted_date = date_str
                    
                    return {
                        "public_law": match.group(1),
                        "date": formatted_date,
                        "raw_date": date_str,
                        "timestamp": datetime.now().isoformat()
                    }
            
            logger.error("Could not find release information on the page")
            return None
        
        except Exception as e:
            logger.error(f"Error getting current release info: {e}")
            return None
    
    def save_release_info(self, release_info):
        """Save release information to a file
        
        Args:
            release_info (dict): Release information
        """
        if not release_info:
            logger.error("No release info to save")
            return
        
        # Create a filename based on the public law
        filename = f"release_{release_info['public_law'].replace('-', '_')}.json"
        file_path = self.versions_dir / filename
        
        try:
            with open(file_path, 'w') as f:
                json.dump(release_info, f, indent=2)
            logger.info(f"Release info saved to {file_path}")
        except Exception as e:
            logger.error(f"Error saving release info: {e}")
    
    def get_latest_saved_release(self):
        """Get the latest saved release information
        
        Returns:
            dict: Release information or None if not found
        """
        try:
            # Get all release files
            release_files = list(self.versions_dir.glob("release_*.json"))
            
            if not release_files:
                logger.info("No saved releases found")
                return None
            
            # Sort by modification time (newest first)
            release_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Load the newest file
            with open(release_files[0], 'r') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error getting latest saved release: {e}")
            return None
    
    def is_new_release_available(self):
        """Check if a new release is available
        
        Returns:
            tuple: (bool, current_release, previous_release)
        """
        # Get current release info
        current_release = self.get_current_release_info()
        if not current_release:
            logger.error("Could not get current release info")
            return False, None, None
        
        # Get latest saved release
        previous_release = self.get_latest_saved_release()
        
        # If no previous release, this is the first run
        if not previous_release:
            logger.info("No previous release found, this is the first run")
            self.save_release_info(current_release)
            return True, current_release, None
        
        # Check if the public law has changed
        if current_release['public_law'] != previous_release['public_law']:
            logger.info(f"New release available: {previous_release['public_law']} -> {current_release['public_law']}")
            return True, current_release, previous_release
        
        logger.info("No new release available")
        return False, current_release, previous_release
    
    def generate_changelog(self, current_release, previous_release):
        """Generate a changelog between two releases
        
        Args:
            current_release (dict): Current release information
            previous_release (dict): Previous release information
            
        Returns:
            dict: Changelog information
        """
        if not current_release or not previous_release:
            logger.error("Cannot generate changelog without both releases")
            return None
        
        changelog = {
            "from_version": previous_release['public_law'],
            "to_version": current_release['public_law'],
            "from_date": previous_release['date'],
            "to_date": current_release['date'],
            "generated_at": datetime.now().isoformat(),
            "changes": []
        }
        
        # In a real implementation, we would analyze the actual content changes
        # For now, we'll just create a placeholder
        changelog["changes"].append({
            "type": "update",
            "description": f"Updated from Public Law {previous_release['public_law']} to {current_release['public_law']}",
            "details": f"The US Code was updated from the version based on Public Law {previous_release['public_law']} "
                      f"({previous_release['raw_date']}) to the version based on Public Law {current_release['public_law']} "
                      f"({current_release['raw_date']})."
        })
        
        # Save the changelog
        changelog_file = self.changes_dir / f"changelog_{previous_release['public_law'].replace('-', '_')}_to_{current_release['public_law'].replace('-', '_')}.json"
        
        try:
            with open(changelog_file, 'w') as f:
                json.dump(changelog, f, indent=2)
            logger.info(f"Changelog saved to {changelog_file}")
        except Exception as e:
            logger.error(f"Error saving changelog: {e}")
        
        return changelog
    
    def subscribe_to_updates(self, email, title_numbers=None):
        """Subscribe to updates for specific titles or all titles
        
        Args:
            email (str): Email address to subscribe
            title_numbers (list): List of title numbers to subscribe to, or None for all
            
        Returns:
            bool: True if subscription was successful
        """
        if not email or '@' not in email:
            logger.error(f"Invalid email address: {email}")
            return False
        
        # Create a subscriber file
        subscriber_file = self.subscribers_dir / f"{email.replace('@', '_at_')}.json"
        
        subscription = {
            "email": email,
            "subscribed_at": datetime.now().isoformat(),
            "title_numbers": title_numbers,
            "active": True
        }
        
        try:
            with open(subscriber_file, 'w') as f:
                json.dump(subscription, f, indent=2)
            logger.info(f"Subscription saved for {email}")
            return True
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
            return False
    
    def unsubscribe_from_updates(self, email):
        """Unsubscribe from updates
        
        Args:
            email (str): Email address to unsubscribe
            
        Returns:
            bool: True if unsubscription was successful
        """
        if not email or '@' not in email:
            logger.error(f"Invalid email address: {email}")
            return False
        
        # Find the subscriber file
        subscriber_file = self.subscribers_dir / f"{email.replace('@', '_at_')}.json"
        
        if not subscriber_file.exists():
            logger.error(f"No subscription found for {email}")
            return False
        
        try:
            # Load the subscription
            with open(subscriber_file, 'r') as f:
                subscription = json.load(f)
            
            # Mark as inactive
            subscription['active'] = False
            subscription['unsubscribed_at'] = datetime.now().isoformat()
            
            # Save the updated subscription
            with open(subscriber_file, 'w') as f:
                json.dump(subscription, f, indent=2)
            
            logger.info(f"Unsubscribed {email}")
            return True
        
        except Exception as e:
            logger.error(f"Error unsubscribing {email}: {e}")
            return False
    
    def get_active_subscribers(self, title_number=None):
        """Get all active subscribers, optionally filtered by title number
        
        Args:
            title_number (int): Title number to filter by, or None for all
            
        Returns:
            list: List of subscriber dictionaries
        """
        subscribers = []
        
        try:
            # Get all subscriber files
            subscriber_files = list(self.subscribers_dir.glob("*.json"))
            
            for file in subscriber_files:
                with open(file, 'r') as f:
                    subscription = json.load(f)
                
                # Check if active
                if not subscription.get('active', True):
                    continue
                
                # Check if subscribed to the specified title
                if title_number is not None:
                    title_numbers = subscription.get('title_numbers')
                    if title_numbers is not None and title_number not in title_numbers:
                        continue
                
                subscribers.append(subscription)
            
            return subscribers
        
        except Exception as e:
            logger.error(f"Error getting active subscribers: {e}")
            return []
    
    def send_update_notification(self, changelog, subscribers=None):
        """Send update notification to subscribers
        
        Args:
            changelog (dict): Changelog information
            subscribers (list): List of subscribers to notify, or None for all active
            
        Returns:
            int: Number of notifications sent
        """
        if not self.config['email_notifications']['enabled']:
            logger.info("Email notifications are disabled")
            return 0
        
        if not changelog:
            logger.error("No changelog provided")
            return 0
        
        # Get subscribers if not provided
        if subscribers is None:
            subscribers = self.get_active_subscribers()
        
        if not subscribers:
            logger.info("No subscribers to notify")
            return 0
        
        # Set up email
        smtp_server = self.config['email_notifications']['smtp_server']
        smtp_port = self.config['email_notifications']['smtp_port']
        username = self.config['email_notifications']['username']
        password = self.config['email_notifications']['password']
        from_address = self.config['email_notifications']['from_address']
        
        if not smtp_server or not username or not password or not from_address:
            logger.error("Email configuration is incomplete")
            return 0
        
        # Create email content
        subject = f"US Code Update: Public Law {changelog['from_version']} to {changelog['to_version']}"
        
        # Create HTML content
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #3498db; }}
                .change {{ margin-bottom: 20px; }}
                .change-type {{ font-weight: bold; color: #e74c3c; }}
                .footer {{ margin-top: 30px; font-size: 0.8em; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>US Code Update Notification</h1>
            <p>The US Code has been updated from Public Law {changelog['from_version']} ({changelog['from_date']}) 
            to Public Law {changelog['to_version']} ({changelog['to_date']}).</p>
            
            <h2>Changes</h2>
        """
        
        for change in changelog['changes']:
            html_content += f"""
            <div class="change">
                <p><span class="change-type">{change['type'].upper()}:</span> {change['description']}</p>
                <p>{change['details']}</p>
            </div>
            """
        
        html_content += f"""
            <div class="footer">
                <p>This is an automated notification from the US Code Browser.</p>
                <p>To unsubscribe from these notifications, please reply to this email with "UNSUBSCRIBE" in the subject line.</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text content
        text_content = f"""
US Code Update Notification

The US Code has been updated from Public Law {changelog['from_version']} ({changelog['from_date']}) 
to Public Law {changelog['to_version']} ({changelog['to_date']}).

Changes:
"""
        
        for change in changelog['changes']:
            text_content += f"""
{change['type'].upper()}: {change['description']}
{change['details']}

"""
        
        text_content += """
This is an automated notification from the US Code Browser.
To unsubscribe from these notifications, please reply to this email with "UNSUBSCRIBE" in the subject line.
"""
        
        # Send emails
        notifications_sent = 0
        
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(username, password)
            
            for subscriber in subscribers:
                try:
                    # Create message
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    msg['From'] = from_address
                    msg['To'] = subscriber['email']
                    
                    # Attach parts
                    part1 = MIMEText(text_content, 'plain')
                    part2 = MIMEText(html_content, 'html')
                    msg.attach(part1)
                    msg.attach(part2)
                    
                    # Send email
                    server.sendmail(from_address, subscriber['email'], msg.as_string())
                    notifications_sent += 1
                    logger.info(f"Notification sent to {subscriber['email']}")
                
                except Exception as e:
                    logger.error(f"Error sending notification to {subscriber['email']}: {e}")
            
            # Close connection
            server.quit()
            
        except Exception as e:
            logger.error(f"Error connecting to SMTP server: {e}")
        
        return notifications_sent

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='US Code Update Tracker')
    parser.add_argument('--check', action='store_true', help='Check for updates')
    parser.add_argument('--subscribe', metavar='EMAIL', help='Subscribe to updates')
    parser.add_argument('--unsubscribe', metavar='EMAIL', help='Unsubscribe from updates')
    parser.add_argument('--titles', metavar='TITLES', help='Comma-separated list of title numbers (for --subscribe)')
    parser.add_argument('--notify', action='store_true', help='Send notifications for the latest update')
    parser.add_argument('--config', action='store_true', help='Configure email settings')
    
    args = parser.parse_args()
    
    tracker = USCodeUpdateTracker()
    
    if args.check:
        is_new, current, previous = tracker.is_new_release_available()
        if is_new and current and previous:
            changelog = tracker.generate_changelog(current, previous)
            tracker.save_release_info(current)
            
            if changelog:
                print(f"New release available: {previous['public_law']} -> {current['public_law']}")
                print(f"Changelog generated: {len(changelog['changes'])} changes")
            
    elif args.subscribe:
        title_numbers = None
        if args.titles:
            try:
                title_numbers = [int(t.strip()) for t in args.titles.split(',')]
                print(f"Subscribing {args.subscribe} to titles: {title_numbers}")
            except ValueError:
                print("Invalid title numbers. Please provide comma-separated integers.")
                exit(1)
        else:
            print(f"Subscribing {args.subscribe} to all titles")
        
        success = tracker.subscribe_to_updates(args.subscribe, title_numbers)
        if success:
            print(f"Successfully subscribed {args.subscribe}")
        else:
            print(f"Failed to subscribe {args.subscribe}")
    
    elif args.unsubscribe:
        success = tracker.unsubscribe_from_updates(args.unsubscribe)
        if success:
            print(f"Successfully unsubscribed {args.unsubscribe}")
        else:
            print(f"Failed to unsubscribe {args.unsubscribe}")
    
    elif args.notify:
        # Get the latest changelog
        latest_release = tracker.get_latest_saved_release()
        if not latest_release:
            print("No saved releases found")
            exit(1)
        
        # Find the latest changelog file
        changelog_files = list(tracker.changes_dir.glob("changelog_*.json"))
        if not changelog_files:
            print("No changelog files found")
            exit(1)
        
        # Sort by modification time (newest first)
        changelog_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Load the newest changelog
        with open(changelog_files[0], 'r') as f:
            changelog = json.load(f)
        
        # Send notifications
        count = tracker.send_update_notification(changelog)
        print(f"Sent {count} notifications")
    
    elif args.config:
        print("Configuring email settings:")
        
        tracker.config['email_notifications']['enabled'] = input("Enable email notifications? (y/n): ").lower() == 'y'
        
        if tracker.config['email_notifications']['enabled']:
            tracker.config['email_notifications']['smtp_server'] = input("SMTP server: ")
            tracker.config['email_notifications']['smtp_port'] = int(input("SMTP port: "))
            tracker.config['email_notifications']['username'] = input("SMTP username: ")
            tracker.config['email_notifications']['password'] = input("SMTP password: ")
            tracker.config['email_notifications']['from_address'] = input("From email address: ")
        
        tracker.save_config()
        print("Configuration saved")
    
    else:
        parser.print_help()
