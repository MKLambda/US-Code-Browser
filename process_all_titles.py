import argparse
from pathlib import Path
import time
import logging
from download_usc_releases import USCReleaseDownloader, find_all_release_points
from usc_processor import USCProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('process_all_titles.log')
    ]
)

logger = logging.getLogger('process_all_titles')

def download_and_process_title(title_num, download_dir="downloads", output_dir="processed", force_download=False):
    """Download and process a specific title"""
    # Initialize downloader and processor
    downloader = USCReleaseDownloader(download_dir=download_dir)
    processor = USCProcessor(download_dir=download_dir, output_dir=output_dir)

    # Format title number with leading zeros
    title_str = str(title_num).zfill(2)

    # Check if we already have the processed JSON file
    json_pattern = f"title{title_str}_*.json"
    existing_json = list(Path(output_dir).glob(json_pattern))

    if existing_json and not force_download:
        logger.info(f"Title {title_str} already processed: {existing_json[0].name}")
        return True

    # Find the latest release for this title
    all_releases = find_all_release_points()

    if title_num not in all_releases:
        logger.error(f"No release found for Title {title_str}")
        return False

    # Get the latest release
    latest_release = all_releases[title_num][0]
    release_info = latest_release['release']
    url = latest_release['url']

    # Construct the output filename
    output_filename = f"title{title_str}_{release_info}.zip"
    output_path = Path(download_dir) / output_filename

    # Check if we already have the downloaded file
    if output_path.exists() and not force_download:
        logger.info(f"Title {title_str} already downloaded: {output_filename}")
    else:
        # Download the file
        logger.info(f"Downloading Title {title_str} (Release {release_info})...")
        success = downloader.download_from_direct_url(url, output_filename)
        if not success:
            logger.error(f"Failed to download Title {title_str}")
            return False

    # Process the file
    logger.info(f"Processing Title {title_str}...")
    processor.process_zip_file(output_path)

    return True

def process_all_titles(download_dir="downloads", output_dir="processed", force_download=False):
    """Download and process all titles"""
    # Find all available titles
    all_releases = find_all_release_points()

    if not all_releases:
        logger.error("No releases found")
        return

    # Create directories if they don't exist
    Path(download_dir).mkdir(exist_ok=True)
    Path(output_dir).mkdir(exist_ok=True)

    # Process each title
    total_titles = len(all_releases)
    successful = 0

    for title_num in sorted(all_releases.keys()):
        logger.info(f"Processing Title {title_num} ({successful+1}/{total_titles})...")

        try:
            success = download_and_process_title(
                title_num,
                download_dir=download_dir,
                output_dir=output_dir,
                force_download=force_download
            )

            if success:
                successful += 1

            # Add a small delay between titles
            time.sleep(1)

        except Exception as e:
            logger.error(f"Error processing Title {title_num}: {e}")

    logger.info(f"Processed {successful} out of {total_titles} titles successfully")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download and process USC titles')
    parser.add_argument('--title', type=int, help='Process a specific title')
    parser.add_argument('--all', action='store_true', help='Process all titles')
    parser.add_argument('--download-dir', default='downloads', help='Directory for downloaded files')
    parser.add_argument('--output-dir', default='processed', help='Directory for processed JSON files')
    parser.add_argument('--force', action='store_true', help='Force download even if files exist')

    args = parser.parse_args()

    if args.title:
        # Process a specific title
        download_and_process_title(
            args.title,
            download_dir=args.download_dir,
            output_dir=args.output_dir,
            force_download=args.force
        )
    elif args.all:
        # Process all titles
        process_all_titles(
            download_dir=args.download_dir,
            output_dir=args.output_dir,
            force_download=args.force
        )
    else:
        # Default: process Title 1 using the direct URL
        title1_url = "https://uscode.house.gov/download/releasepoints/us/pl/119/4/xml_usc01@119-4.zip"
        output_filename = "title01_119-4.zip"

        # Initialize downloader and processor
        downloader = USCReleaseDownloader(download_dir=args.download_dir)
        processor = USCProcessor(download_dir=args.download_dir, output_dir=args.output_dir)

        # Download Title 1
        output_path = Path(args.download_dir) / output_filename
        if not output_path.exists() or args.force:
            logger.info(f"Downloading Title 1 from {title1_url}...")
            downloader.download_from_direct_url(title1_url, output_filename)

        # Process Title 1
        logger.info(f"Processing Title 1...")
        processor.process_zip_file(output_path)

        print("\nTo process other titles, use the --title or --all options.")
