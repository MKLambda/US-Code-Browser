# US Code Browser

## Overview

The US Code Browser is a comprehensive tool for accessing, searching, and analyzing the United States Code (USC). It downloads the official USC XML files from the Office of the Law Revision Counsel (OLRC) of the U.S. House of Representatives, processes them into a structured format, and provides both a web interface and API for easy access.

This project aims to make the US Code more accessible and usable for legal professionals, researchers, developers, and the general public.

## Key Features

### Core Functionality
- **Automated Downloads**: Retrieves USC XML files from official government sources
- **Structured Data**: Processes XML into JSON format with proper hierarchical structure
- **Complete Coverage**: Handles all 54 titles of the USC (Title 53 is reserved)
- **Regular Updates**: Automatically checks for and processes new releases every 30 days

### User Interface
- **Modern Web Interface**: Clean, responsive design for browsing the USC
- **Advanced Search**: Full-text search across all titles with filtering options
- **Legal Term Definitions**: Click-to-view definitions of legal terms
- **Citation Tools**: Easy copying of proper legal citations

### Developer Tools
- **RESTful API**: Comprehensive API for programmatic access to USC data
- **Webhook Integrations**: Real-time notifications when the USC is updated
- **Diff Visualization**: Visual comparison between different versions of the USC

### Advanced Features
- **Change Tracking**: Detailed tracking of changes between USC versions
- **Email Notifications**: Subscribe to receive updates when specific titles change
- **Performance Optimizations**: Caching and efficient data processing

## Installation

### Prerequisites
- Python 3.8 or higher
- 2GB+ of free disk space (for storing USC data)
- Internet connection (for downloading USC files)

### Basic Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/MKLambda/US-Code-Browser.git
   cd us-code-browser
   ```

2. **Install required packages**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create necessary directories**
   ```bash
   python setup.py
   ```

4. **Download and process a sample title**
   ```bash
   python process_all_titles.py --title 1
   ```

5. **Start the web interface**
   ```bash
   python web_interface.py
   ```

6. **Access the web interface**
   Open your browser and navigate to http://localhost:5000

### Full Installation

To download and process all titles of the USC (this may take some time):

```bash
python process_all_titles.py --all
```

## Usage Guide

### Web Interface

The web interface provides a user-friendly way to browse and search the USC:

1. **Home Page**: Lists all titles of the USC with descriptions
2. **Title View**: Shows chapters and sections within a title
3. **Section View**: Displays the full text of a section with proper formatting
4. **Search**: Use the search bar to find specific terms across all titles
5. **Updates**: View the history of USC updates and subscribe to notifications
6. **Diff View**: Compare different versions of the USC to see what changed

### API Usage

The RESTful API provides programmatic access to the USC data:

```bash
# Get a list of all titles
curl http://localhost:5000/api/titles

# Get data for a specific title
curl http://localhost:5000/api/titles/1

# Get data for a specific chapter
curl http://localhost:5000/api/titles/1/chapters/1

# Get data for a specific section
curl http://localhost:5000/api/titles/1/chapters/1/sections/1

# Search for a term
curl http://localhost:5000/api/search?q=congress
```

### Webhook Integration

Register a webhook to receive notifications when the USC is updated:

```bash
curl -X POST http://localhost:5000/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-server.com/webhook", "events": ["update.released", "update.processed"], "description": "My USC update webhook"}'
```

### Regular Updates

Set up scheduled updates to automatically check for new USC releases:

```bash
python enhanced_updates.py --setup
```

## Use Cases

### Legal Research
- **Case Preparation**: Quickly find relevant statutes for legal cases
- **Legal Writing**: Easily cite and reference USC sections in legal documents
- **Compliance**: Stay updated on changes to relevant laws and regulations

### Academic Research
- **Legal Studies**: Analyze the structure and content of federal laws
- **Policy Analysis**: Track changes to legislation over time
- **Data Mining**: Extract patterns and insights from legal text

### Software Development
- **Legal Tech Applications**: Integrate USC data into legal technology solutions
- **Compliance Software**: Build tools that monitor relevant regulatory changes
- **Educational Tools**: Create interactive learning resources about federal law

### Government and Public Service
- **Policy Development**: Reference current laws when drafting new legislation
- **Public Information**: Provide accessible legal information to constituents
- **Regulatory Compliance**: Monitor changes to relevant regulations

## Advanced Configuration

### Performance Tuning

For large-scale deployments or systems with limited resources:

```python
# In web_interface.py, adjust the cache settings
CACHE_TIMEOUT = 3600  # Cache timeout in seconds
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Max content size in bytes
```

### Custom Deployment

For production deployment with a WSGI server:

```bash
# Using Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web_interface:app

# Using uWSGI
pip install uwsgi
uwsgi --http :5000 --wsgi-file web_interface.py --callable app --processes 4 --threads 2
```

## Troubleshooting

### Common Issues

#### Download Problems

If you encounter issues downloading USC files:

```bash
# Check available release points
python download_usc_releases.py --list

# Force re-download of a specific title
python download_usc_releases.py --title 1 --force
```

#### Processing Errors

If you encounter errors during processing:

```bash
# Process with debug logging
python process_all_titles.py --title 1 --debug

# Verify processed titles
python verify_titles.py
```

#### Web Interface Issues

If the web interface is not displaying correctly:

1. Check that the templates directory contains all necessary template files
2. Verify that the static directory contains the CSS and JavaScript files
3. Check the web_interface.log file for specific error messages

## API Documentation

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/titles` | GET | List all titles |
| `/api/titles/<title_num>` | GET | Get data for a specific title |
| `/api/titles/<title_num>/chapters/<chapter_num>` | GET | Get data for a specific chapter |
| `/api/titles/<title_num>/chapters/<chapter_num>/sections/<section_num>` | GET | Get data for a specific section |
| `/api/search` | GET | Search for terms across all titles |
| `/api/webhooks` | GET/POST | List or register webhooks |
| `/api/webhooks/<webhook_id>` | GET/PUT/DELETE | Manage a specific webhook |
| `/api/diff/<title_num>` | GET | Get diff between versions of a title |

### Example Response

```json
{
  "title_num": 1,
  "name": "General Provisions",
  "chapters": [
    {
      "num": "1",
      "heading": "Rules of Construction",
      "sections": [
        {
          "num": "1",
          "heading": "Words denoting number, gender, and so forth",
          "content": "In determining the meaning of any Act of Congress, unless the context indicates otherwise..."
        }
      ]
    }
  ]
}
```

## Contributing

Contributions to the US Code Browser are welcome! Here's how you can help:

1. **Report Issues**: Submit bug reports or feature requests through the issue tracker
2. **Suggest Improvements**: Provide feedback on the user interface or API
3. **Submit Pull Requests**: Contribute code improvements or new features
4. **Improve Documentation**: Help enhance the documentation and examples

Please follow the existing code style and include appropriate tests with your contributions.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- The United States Code is provided by the Office of the Law Revision Counsel (OLRC) of the U.S. House of Representatives
- The XML files are in the United States Legislative Markup (USLM) format
- This project is not affiliated with or endorsed by the U.S. government
