import requests
import os
from pathlib import Path
import time

class USCDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = Path(download_dir)
        self.base_url = "https://uscode.house.gov/download/"
        self.download_dir.mkdir(exist_ok=True)

    def download_title(self, title_number):
        """Download a specific USC title"""
        # Format title number with leading zeros if needed
        title_str = str(title_number).zfill(2)

        # Construct the URL for the title
        url = f"{self.base_url}title{title_str}.zip"

        # Construct the output file path
        output_file = self.download_dir / f"title{title_str}.zip"

        print(f"Downloading Title {title_str} from {url}...")

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

    def download_all_titles(self):
        """Download all USC titles (1-54)"""
        # There are 54 titles in the USC
        for title_number in range(1, 55):
            success = self.download_title(title_number)

            # Add a small delay between requests to be nice to the server
            if success:
                time.sleep(1)

if __name__ == "__main__":
    downloader = USCDownloader()

    # Download Title 1 for testing
    downloader.download_title(1)
