import argparse
import logging
import os
import sys
import time
from pathlib import Path
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('run_all.log')
    ]
)

logger = logging.getLogger('run_all')

def run_command(command, description):
    """Run a command and log the output"""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {command}")
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            universal_newlines=True
        )
        
        # Stream output
        for line in process.stdout:
            logger.info(line.strip())
        
        # Wait for process to complete
        process.wait()
        
        # Check return code
        if process.returncode != 0:
            logger.error(f"Command failed with return code {process.returncode}")
            for line in process.stderr:
                logger.error(line.strip())
            return False
        
        logger.info(f"Command completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False

def setup_environment():
    """Set up the environment"""
    logger.info("Setting up environment...")
    
    # Create directories
    directories = [
        "downloads",
        "processed",
        "advanced_processed",
        "analysis_results",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    # Install requirements
    run_command("pip install -r requirements.txt", "Installing requirements")

def download_titles(title_num=None):
    """Download titles"""
    if title_num:
        logger.info(f"Downloading Title {title_num}...")
        return run_command(f"python process_all_titles.py --title {title_num}", f"Downloading Title {title_num}")
    else:
        logger.info("Downloading all titles...")
        return run_command("python process_all_titles.py --all", "Downloading all titles")

def process_titles():
    """Process downloaded titles"""
    logger.info("Processing titles...")
    return run_command("python usc_processor.py", "Processing titles")

def run_advanced_processing():
    """Run advanced processing"""
    logger.info("Running advanced processing...")
    return run_command("python advanced_processor.py", "Advanced processing")

def run_data_analysis():
    """Run data analysis"""
    logger.info("Running data analysis...")
    return run_command("python data_analysis.py", "Data analysis")

def start_web_interface():
    """Start the web interface"""
    logger.info("Starting web interface...")
    return run_command("start python web_interface.py", "Web interface")

def start_api():
    """Start the API"""
    logger.info("Starting API...")
    return run_command("start python api.py", "API")

def setup_scheduled_updates():
    """Set up scheduled updates"""
    logger.info("Setting up scheduled updates...")
    return run_command("python scheduled_updates.py --setup", "Scheduled updates")

def run_all(args):
    """Run all components"""
    # Set up environment
    setup_environment()
    
    # Download titles
    if args.download:
        if args.title:
            download_titles(args.title)
        else:
            download_titles()
    
    # Process titles
    if args.process:
        process_titles()
    
    # Run advanced processing
    if args.advanced:
        run_advanced_processing()
    
    # Run data analysis
    if args.analysis:
        run_data_analysis()
    
    # Start web interface
    if args.web:
        start_web_interface()
    
    # Start API
    if args.api:
        start_api()
    
    # Set up scheduled updates
    if args.schedule:
        setup_scheduled_updates()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run all components of the US Laws Processor')
    parser.add_argument('--download', action='store_true', help='Download titles')
    parser.add_argument('--title', type=int, help='Download a specific title')
    parser.add_argument('--process', action='store_true', help='Process titles')
    parser.add_argument('--advanced', action='store_true', help='Run advanced processing')
    parser.add_argument('--analysis', action='store_true', help='Run data analysis')
    parser.add_argument('--web', action='store_true', help='Start web interface')
    parser.add_argument('--api', action='store_true', help='Start API')
    parser.add_argument('--schedule', action='store_true', help='Set up scheduled updates')
    parser.add_argument('--all', action='store_true', help='Run all components')
    
    args = parser.parse_args()
    
    # If --all is specified, run everything
    if args.all:
        args.download = True
        args.process = True
        args.advanced = True
        args.analysis = True
        args.web = True
        args.api = True
        args.schedule = True
    
    # If no arguments are specified, show help
    if not any(vars(args).values()):
        parser.print_help()
    else:
        run_all(args)
