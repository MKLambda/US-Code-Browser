import subprocess
import sys
import time
import os

def run_command(command):
    """Run a command and print the output"""
    print(f"Running: {command}")
    
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
            print(line.strip())
        
        # Wait for process to complete
        process.wait()
        
        # Check return code
        if process.returncode != 0:
            print(f"Command failed with return code {process.returncode}")
            for line in process.stderr:
                print(line.strip())
            return False
        
        print(f"Command completed successfully")
        return True
    
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def install_requirements():
    """Install requirements incrementally"""
    # Basic requirements (should work on all systems)
    basic_requirements = [
        "requests",
        "beautifulsoup4",
        "Flask"
    ]
    
    # Advanced requirements (may require compilation)
    advanced_requirements = [
        "Flask-RESTful",
        "pandas",
        "matplotlib",
        "seaborn",
        "nltk"
    ]
    
    # Optional requirements (may be difficult to install)
    optional_requirements = [
        "scikit-learn",
        "networkx"
    ]
    
    # Install basic requirements
    print("Installing basic requirements...")
    for req in basic_requirements:
        if not run_command(f"{sys.executable} -m pip install {req}"):
            print(f"Failed to install {req}")
            return False
    
    # Install advanced requirements
    print("\nInstalling advanced requirements...")
    for req in advanced_requirements:
        if not run_command(f"{sys.executable} -m pip install {req}"):
            print(f"Failed to install {req}, but continuing...")
    
    # Install optional requirements
    print("\nInstalling optional requirements...")
    for req in optional_requirements:
        if not run_command(f"{sys.executable} -m pip install {req}"):
            print(f"Failed to install {req}, but continuing...")
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = [
        "downloads",
        "processed",
        "advanced_processed",
        "analysis_results",
        "logs",
        "templates",
        "static"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

if __name__ == "__main__":
    print("Setting up US Laws Processor...")
    
    # Create directories
    create_directories()
    
    # Install requirements
    if install_requirements():
        print("\nSetup completed successfully!")
        print("\nYou can now run the following commands:")
        print("  python download_usc_releases.py --list  # List available titles")
        print("  python process_all_titles.py --title 1  # Download and process Title 1")
        print("  python web_interface.py                 # Start the web interface")
        print("  python api.py                           # Start the API")
    else:
        print("\nSetup failed. Please check the error messages above.")
