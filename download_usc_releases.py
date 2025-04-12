import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
import time

class USCReleaseDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = Path(download_dir)
        self.base_url = "https://uscode.house.gov/download/releasepoints/"
        self.download_dir.mkdir(exist_ok=True)

    def find_latest_releases(self):
        """Find the latest release points for all titles"""
        print("Finding latest release points for all titles...")

        # Dictionary to store the latest release for each title
        latest_releases = {}

        try:
            # Get the release points page
            response = requests.get("https://uscode.house.gov/download/download.shtml")
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all links that match the release point pattern
            links = soup.find_all('a', href=re.compile(r'releasepoints/.*\.zip'))

            # Extract title numbers and release points
            for link in links:
                href = link.get('href')
                # Extract title number and release info from the URL
                match = re.search(r'xml_usc(\d+)@(\d+-\d+)\.zip', href)
                if match:
                    title_num = int(match.group(1))
                    release_info = match.group(2)

                    # Store the full URL
                    full_url = f"https://uscode.house.gov/download/{href}"

                    # Update the latest release for this title
                    if title_num not in latest_releases or release_info > latest_releases[title_num]['release']:
                        latest_releases[title_num] = {
                            'release': release_info,
                            'url': full_url
                        }

            print(f"Found latest releases for {len(latest_releases)} titles.")
            return latest_releases

        except Exception as e:
            print(f"Error finding latest releases: {e}")
            return {}

    def download_release(self, title_number, release_info):
        """Download a specific USC title release"""
        url = release_info['url']
        release = release_info['release']

        # Format title number with leading zeros if needed
        title_str = str(title_number).zfill(2)

        # Construct the output file path
        output_file = self.download_dir / f"title{title_str}_{release}.zip"

        print(f"Downloading Title {title_str} (Release {release}) from {url}...")

        try:
            # Send a GET request to the URL
            response = requests.get(url, stream=True)

            # Check if the request was successful
            if response.status_code == 200:
                # Write the content to the output file
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"Successfully downloaded Title {title_str} to {output_file}")
                return True
            else:
                print(f"Failed to download Title {title_str}. Status code: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error downloading Title {title_str}: {e}")
            return False

    def download_all_latest_releases(self):
        """Download the latest release for all titles"""
        # Find the latest releases
        latest_releases = self.find_latest_releases()

        if not latest_releases:
            print("No releases found. Exiting.")
            return

        # Download each release
        for title_num, release_info in sorted(latest_releases.items()):
            success = self.download_release(title_num, release_info)

            # Add a small delay between requests to be nice to the server
            if success:
                time.sleep(1)

    def download_specific_title(self, title_number):
        """Download the latest release for a specific title"""
        # Find the latest releases
        latest_releases = self.find_latest_releases()

        if not latest_releases:
            print("No releases found. Exiting.")
            return

        # Check if the requested title exists
        if title_number in latest_releases:
            self.download_release(title_number, latest_releases[title_number])
        else:
            print(f"No release found for Title {title_number}")

    def download_from_direct_url(self, url, output_filename):
        """Download from a direct URL"""
        output_file = self.download_dir / output_filename

        print(f"Downloading from {url}...")

        try:
            # Send a GET request to the URL
            response = requests.get(url, stream=True)

            # Check if the request was successful
            if response.status_code == 200:
                # Write the content to the output file
                with open(output_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"Successfully downloaded to {output_file}")
                return True
            else:
                print(f"Failed to download. Status code: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error downloading: {e}")
            return False

def find_all_release_points():
    """Find all available release points for all titles"""
    import requests
    from bs4 import BeautifulSoup
    import re

    print("Finding all available release points...")

    # Dictionary to store all releases for each title
    all_releases = {}

    try:
        # Get the release points page
        response = requests.get("https://uscode.house.gov/download/download.shtml")
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all links that match the release point pattern
        links = soup.find_all('a', href=re.compile(r'releasepoints/.*\.zip'))

        # Extract title numbers and release info from the URLs
        for link in links:
            href = link.get('href')
            # Extract title number and release info from the URL
            match = re.search(r'xml_usc(\d+)@(\d+-\d+)\.zip', href)
            if match:
                title_num = int(match.group(1))
                release_info = match.group(2)

                # Store the full URL
                full_url = f"https://uscode.house.gov/download/{href}"

                # Add to the releases for this title
                if title_num not in all_releases:
                    all_releases[title_num] = []

                all_releases[title_num].append({
                    'release': release_info,
                    'url': full_url
                })

        # Sort releases for each title
        for title_num in all_releases:
            all_releases[title_num].sort(key=lambda x: x['release'], reverse=True)

        print(f"Found {sum(len(releases) for releases in all_releases.values())} release points for {len(all_releases)} titles.")

        # Print a summary
        for title_num in sorted(all_releases.keys()):
            releases = all_releases[title_num]
            print(f"Title {title_num}: {len(releases)} releases (latest: {releases[0]['release']})")

        return all_releases

    except Exception as e:
        print(f"Error finding release points: {e}")
        return {}

if __name__ == "__main__":
    import argparse

    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Download USC XML files')
    parser.add_argument('--title', type=int, help='Download a specific title')
    parser.add_argument('--all', action='store_true', help='Download all titles')
    parser.add_argument('--list', action='store_true', help='List all available release points')
    parser.add_argument('--output-dir', default='downloads', help='Directory for downloaded files')

    args = parser.parse_args()

    # Initialize downloader
    downloader = USCReleaseDownloader(download_dir=args.output_dir)

    if args.list:
        # Just list all available release points
        find_all_release_points()
    elif args.title:
        # Download a specific title
        downloader.download_specific_title(args.title)
    elif args.all:
        # Download all titles
        downloader.download_all_latest_releases()
    else:
        # Default: download Title 1
        title1_url = "https://uscode.house.gov/download/releasepoints/us/pl/119/4/xml_usc01@119-4.zip"
        downloader.download_from_direct_url(title1_url, "title01_119-4.zip")
        print("\nTo download other titles, use the --title or --all options.")
        print("To see all available release points, use the --list option.")
