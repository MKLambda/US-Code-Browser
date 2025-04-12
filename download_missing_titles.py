import requests
from pathlib import Path
import logging
from usc_processor import USCProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('download_missing_titles.log')
    ]
)

logger = logging.getLogger('download_missing_titles')

def download_file(url, output_path):
    """Download a file from a URL to a specified path"""
    logger.info(f"Downloading from {url}...")
    
    try:
        # Send a GET request to the URL
        response = requests.get(url, stream=True)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Write the content to the output file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Successfully downloaded to {output_path}")
            return True
        else:
            logger.error(f"Failed to download. Status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error downloading: {e}")
        return False

def download_and_process_missing_titles():
    """Download and process missing titles"""
    # Create directories if they don't exist
    download_dir = Path("downloads")
    output_dir = Path("processed")
    download_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # Initialize processor
    processor = USCProcessor(download_dir=str(download_dir), output_dir=str(output_dir))
    
    # List of missing titles
    missing_titles = [31, 36, 47, 53]
    
    for title_num in missing_titles:
        # Format title number with leading zeros
        title_str = str(title_num).zfill(2)
        
        # Construct the URL for the title
        url = f"https://uscode.house.gov/download/releasepoints/us/pl/119/4/xml_usc{title_str}@119-4.zip"
        
        # Construct the output file path
        output_file = download_dir / f"title{title_str}_119-4.zip"
        
        # Download the file
        success = download_file(url, output_file)
        
        if success:
            try:
                # Process the file
                logger.info(f"Processing Title {title_str}...")
                processor.process_zip_file(output_file)
            except Exception as e:
                logger.error(f"Error processing Title {title_str}: {e}")

if __name__ == "__main__":
    download_and_process_missing_titles()
