from flask import Flask, render_template, request, redirect, url_for, Response, jsonify, flash, session
import json
from pathlib import Path
import re
import logging
import traceback
import functools
import time
import gzip
from io import BytesIO
from werkzeug.http import http_date
from datetime import datetime, timedelta

# Import our custom modules
try:
    from update_tracker import USCodeUpdateTracker
except ImportError:
    # Create a stub if the module is not available
    class USCodeUpdateTracker:
        def __init__(self, *args, **kwargs):
            pass

        def get_latest_saved_release(self):
            return {'public_law': '119-4', 'date': '2025-04-11'}

        def get_current_release_info(self):
            return None

        def subscribe_to_updates(self, *args, **kwargs):
            return False

try:
    from webhook_manager import WebhookManager
except ImportError:
    # Create a stub if the module is not available
    class WebhookManager:
        def __init__(self, *args, **kwargs):
            pass

        def register_webhook(self, *args, **kwargs):
            return None

        def trigger_webhooks(self, *args, **kwargs):
            return 0

try:
    from diff_visualizer import DiffVisualizer
except ImportError:
    # Create a stub if the module is not available
    class DiffVisualizer:
        def __init__(self, *args, **kwargs):
            pass

        def get_available_versions(self, *args, **kwargs):
            return ['current']

        def compare_title_versions(self, *args, **kwargs):
            return None

        def generate_html_diff(self, *args, **kwargs):
            return "<p>Diff visualization not available</p>"

# Custom exception classes
class WebInterfaceError(Exception):
    """Base exception for web interface errors"""
    pass

class DataLoadError(WebInterfaceError):
    """Exception raised for data loading errors"""
    pass

class EncodingError(WebInterfaceError):
    """Exception raised for encoding errors"""
    pass

# Create Flask app
app = Flask(__name__)

# Configure secret key for session management
app.secret_key = 'uscode_browser_secret_key'  # In production, use a proper secret key

# Initialize components
update_tracker = USCodeUpdateTracker(data_dir="update_data")
webhook_manager = WebhookManager(data_dir="webhook_data")
diff_visualizer = DiffVisualizer(data_dir="diff_data")

# Cache settings
CACHE_TIMEOUT = 3600  # Cache timeout in seconds (1 hour)
CACHE_ENABLED = True  # Enable/disable caching

# In-memory cache for title data
title_cache = {}
# In-memory cache for all titles list
all_titles_cache = {'data': None, 'timestamp': 0}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('web_interface.log')
    ]
)

logger = logging.getLogger('web_interface')

# Compression threshold in bytes
COMPRESSION_THRESHOLD = 1024  # Only compress responses larger than 1KB

# Cache control decorator
def cache_control(max_age=CACHE_TIMEOUT):
    """Decorator to add cache control headers to responses

    Args:
        max_age (int): Maximum age for the cache in seconds
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(*args, **kwargs):
            response = view_func(*args, **kwargs)

            # Only add cache headers to successful responses
            if isinstance(response, tuple):
                response_obj, status_code = response
                if status_code == 200 and hasattr(response_obj, 'headers'):
                    response_obj.headers['Cache-Control'] = f'public, max-age={max_age}'
                    response_obj.headers['Expires'] = http_date(time.time() + max_age)
            elif hasattr(response, 'headers'):
                response.headers['Cache-Control'] = f'public, max-age={max_age}'
                response.headers['Expires'] = http_date(time.time() + max_age)

            return response
        return wrapped_view
    return decorator

# Compression middleware
@app.after_request
def add_compression(response):
    """Add compression to responses if they're large enough"""
    # Skip compression for certain response types
    if response.direct_passthrough or 'Content-Encoding' in response.headers:
        return response

    # Only compress text responses
    content_type = response.headers.get('Content-Type', '')
    if not content_type.startswith(('text/', 'application/json', 'application/javascript', 'application/xml')):
        return response

    # Make sure we have response data
    try:
        response_data = response.get_data()
        if not response_data or len(response_data) < COMPRESSION_THRESHOLD:
            return response
    except Exception as e:
        logger.warning(f"Error getting response data for compression: {e}")
        return response

    # Check if client accepts gzip encoding
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' not in accept_encoding.lower():
        return response

    # Compress the response
    try:
        gzip_buffer = BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(response_data)

        # Update response with compressed data
        response.set_data(gzip_buffer.getvalue())
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.get_data())
        response.headers['Vary'] = 'Accept-Encoding'
    except Exception as e:
        logger.warning(f"Error compressing response: {e}")

    return response

# Configure error handling
@app.errorhandler(404)
def page_not_found(_):
    logger.warning(f"404 error: {request.path}")
    return render_template('error_modern.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"500 error: {str(error)}")
    return render_template('error_modern.html', message="Internal server error. Please try again later."), 500

# Ensure directories exist
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

def load_title_data(title_num, use_cache=True):
    """Load data for a specific title

    Args:
        title_num (int): The title number to load
        use_cache (bool): Whether to use the cache (default: True)

    Returns:
        dict: The title data, or None if not found or on error

    Raises:
        DataLoadError: If there's an error loading the data
        EncodingError: If there's an encoding error that can't be handled
    """
    # Check cache first if enabled
    if CACHE_ENABLED and use_cache and title_num in title_cache:
        cache_entry = title_cache[title_num]
        # Check if cache entry is still valid
        if time.time() - cache_entry['timestamp'] < CACHE_TIMEOUT:
            logger.debug(f"Using cached data for title {title_num}")
            return cache_entry['data']
        else:
            logger.debug(f"Cache expired for title {title_num}")

    try:
        title_str = str(title_num).zfill(2)
        processed_dir = Path("processed")

        if not processed_dir.exists():
            logger.error(f"Processed directory not found: {processed_dir}")
            raise DataLoadError(f"Processed directory not found: {processed_dir}")

        # Find the JSON file for this title
        json_files = list(processed_dir.glob(f"usc{title_str}.json"))
        if not json_files:
            logger.warning(f"Title {title_num} not found in processed directory")
            return None

        # Load the JSON data
        try:
            with open(json_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Successfully loaded title {title_num} with UTF-8 encoding")

            # Cache the data if caching is enabled
            if CACHE_ENABLED:
                title_cache[title_num] = {
                    'data': data,
                    'timestamp': time.time()
                }
                logger.debug(f"Cached data for title {title_num}")

            return data
        except UnicodeDecodeError as e:
            # Try with different encodings if UTF-8 fails
            logger.warning(f"UTF-8 decode error for title {title_num}: {e}")
            try:
                with open(json_files[0], 'r', encoding='latin-1') as f:
                    data = json.load(f)
                logger.warning(f"Successfully loaded title {title_num} with latin-1 encoding")

                # Cache the data if caching is enabled
                if CACHE_ENABLED:
                    title_cache[title_num] = {
                        'data': data,
                        'timestamp': time.time()
                    }
                    logger.debug(f"Cached data for title {title_num} (latin-1 encoding)")

                return data
            except json.JSONDecodeError as e2:
                logger.error(f"JSON decode error for title {title_num} with latin-1 encoding: {e2}")
                raise DataLoadError(f"Invalid JSON format in title {title_num}") from e2
            except Exception as e2:
                logger.error(f"Error loading title {title_num} with alternative encoding: {e2}")
                raise EncodingError(f"Failed to decode title {title_num} with any encoding") from e2
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for title {title_num}: {e}")
            raise DataLoadError(f"Invalid JSON format in title {title_num}") from e
        except Exception as e:
            logger.error(f"Unexpected error loading title {title_num}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise DataLoadError(f"Failed to load title {title_num}") from e
    except (DataLoadError, EncodingError):
        # Re-raise these specific exceptions to be caught by the caller
        raise
    except Exception as e:
        # Catch any other exceptions and convert to DataLoadError
        logger.error(f"Unexpected error in load_title_data for title {title_num}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise DataLoadError(f"Unexpected error loading title {title_num}") from e

def get_all_titles(use_cache=True):
    """Get a list of all available titles

    Args:
        use_cache (bool): Whether to use the cache (default: True)

    Returns:
        list: A list of dictionaries containing title numbers and names

    Raises:
        DataLoadError: If there's an error loading the data directory
    """
    # Check cache first if enabled
    if CACHE_ENABLED and use_cache and all_titles_cache['data'] is not None:
        # Check if cache entry is still valid
        if time.time() - all_titles_cache['timestamp'] < CACHE_TIMEOUT:
            logger.debug("Using cached data for all titles")
            return all_titles_cache['data']
        else:
            logger.debug("Cache expired for all titles")

    try:
        processed_dir = Path("processed")

        if not processed_dir.exists():
            logger.error(f"Processed directory not found: {processed_dir}")
            raise DataLoadError(f"Processed directory not found: {processed_dir}")

        # Get all JSON files in the processed directory
        json_files = list(processed_dir.glob("*.json"))

        if not json_files:
            logger.warning("No JSON files found in processed directory")
            return []

        # Extract title numbers and names
        titles = []
        for json_file in json_files:
            match = re.search(r'usc(\d+)\.json', json_file.name)
            if match:
                title_num = int(match.group(1))

                # Try to get title from cache first
                if CACHE_ENABLED and title_num in title_cache:
                    cache_entry = title_cache[title_num]
                    if time.time() - cache_entry['timestamp'] < CACHE_TIMEOUT:
                        data = cache_entry['data']
                        logger.debug(f"Using cached data for title {title_num} in get_all_titles")
                    else:
                        # Load the title data to get the name
                        data = load_title_data(title_num, use_cache=False)
                else:
                    # Load the title data to get the name
                    try:
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            # Cache individual title data
                            if CACHE_ENABLED:
                                title_cache[title_num] = {
                                    'data': data,
                                    'timestamp': time.time()
                                }
                        except UnicodeDecodeError as e:
                            # Try with different encodings if UTF-8 fails
                            logger.warning(f"UTF-8 decode error for {json_file.name}: {e}")
                            try:
                                with open(json_file, 'r', encoding='latin-1') as f:
                                    data = json.load(f)
                                logger.warning(f"Successfully loaded {json_file.name} with latin-1 encoding")

                                # Cache individual title data
                                if CACHE_ENABLED:
                                    title_cache[title_num] = {
                                        'data': data,
                                        'timestamp': time.time()
                                    }
                            except Exception as e2:
                                logger.error(f"Error loading {json_file.name} with alternative encoding: {e2}")
                                # Use a fallback for the title name
                                data = {"content": {"title": {"heading": f"Title {title_num}"}}}
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error for {json_file.name}: {e}")
                            # Use a fallback for the title name
                            data = {"content": {"title": {"heading": f"Title {title_num}"}}}
                        except Exception as e:
                            logger.error(f"Unexpected error loading {json_file.name}: {e}")
                            # Use a fallback for the title name
                            data = {"content": {"title": {"heading": f"Title {title_num}"}}}
                    except Exception as e:
                        logger.error(f"Error processing title data for {json_file}: {e}")
                        # Use a fallback for the title name
                        data = {"content": {"title": {"heading": f"Title {title_num}"}}}

                # Extract the title name with fallback
                try:
                    title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"
                except Exception:
                    title_name = f"Title {title_num}"

                titles.append({
                    'number': title_num,
                    'name': title_name
                })

        # Sort titles by number
        titles.sort(key=lambda x: x['number'])

        # Cache the titles list if caching is enabled
        if CACHE_ENABLED:
            all_titles_cache['data'] = titles
            all_titles_cache['timestamp'] = time.time()
            logger.debug("Cached all titles list")

        return titles
    except DataLoadError:
        # Re-raise this specific exception to be caught by the caller
        raise
    except Exception as e:
        # Catch any other exceptions and convert to DataLoadError
        logger.error(f"Unexpected error in get_all_titles: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise DataLoadError(f"Failed to load titles list") from e

def search_titles(query, filters=None, use_cache=True):
    """Search all titles for a specific query with advanced features

    Args:
        query (str): The search query
        filters (dict, optional): Filters to apply to the search (e.g., title_num, chapter_num)
        use_cache (bool, optional): Whether to use cached data

    Returns:
        list: A list of dictionaries containing search results

    Raises:
        DataLoadError: If there's an error loading the data directory
    """
    try:
        # Normalize the query for better matching
        query = query.lower().strip()
        if not query:
            return []

        # Parse the query for exact phrases (in quotes)
        exact_phrases = []
        query_without_quotes = query
        for match in re.finditer(r'"([^"]+)"', query):
            exact_phrase = match.group(1).lower()
            exact_phrases.append(exact_phrase)
            query_without_quotes = query_without_quotes.replace(f'"{exact_phrase}"', '')

        # Get individual terms (excluding exact phrases)
        terms = [term.strip() for term in query_without_quotes.split() if term.strip()]

        # Initialize filters if not provided
        if filters is None:
            filters = {}

        processed_dir = Path("processed")

        if not processed_dir.exists():
            logger.error(f"Processed directory not found: {processed_dir}")
            raise DataLoadError(f"Processed directory not found: {processed_dir}")

        # Get all JSON files in the processed directory, filtered by title if specified
        if 'title_num' in filters and filters['title_num']:
            title_str = str(filters['title_num']).zfill(2)
            json_files = list(processed_dir.glob(f"usc{title_str}.json"))
        else:
            json_files = list(processed_dir.glob("*.json"))

        if not json_files:
            logger.warning("No JSON files found in processed directory")
            return []

        # Search each file for the query
        results = []
        for json_file in json_files:
            match = re.search(r'usc(\d+)\.json', json_file.name)
            if match:
                title_num = int(match.group(1))

                # Skip if title doesn't match filter
                if 'title_num' in filters and filters['title_num'] and title_num != filters['title_num']:
                    continue

                # Load the title data, using cache if enabled
                try:
                    if use_cache and CACHE_ENABLED and title_num in title_cache:
                        cache_entry = title_cache[title_num]
                        if time.time() - cache_entry['timestamp'] < CACHE_TIMEOUT:
                            data = cache_entry['data']
                            logger.debug(f"Using cached data for title {title_num} in search")
                        else:
                            data = load_title_data(title_num, use_cache=False)
                    else:
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            # Cache the data if caching is enabled
                            if CACHE_ENABLED:
                                title_cache[title_num] = {
                                    'data': data,
                                    'timestamp': time.time()
                                }
                        except UnicodeDecodeError as e:
                            # Try with different encodings if UTF-8 fails
                            logger.warning(f"UTF-8 decode error for {json_file.name} during search: {e}")
                            try:
                                with open(json_file, 'r', encoding='latin-1') as f:
                                    data = json.load(f)
                                logger.warning(f"Successfully loaded {json_file.name} with latin-1 encoding for search")

                                # Cache the data if caching is enabled
                                if CACHE_ENABLED:
                                    title_cache[title_num] = {
                                        'data': data,
                                        'timestamp': time.time()
                                    }
                            except Exception as e2:
                                logger.error(f"Error loading {json_file.name} with alternative encoding for search: {e2}")
                                continue  # Skip this file

                    # Extract title name with fallback
                    try:
                        title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"
                    except Exception:
                        title_name = f"Title {title_num}"

                    # Find specific sections that match the query
                    matching_sections = []
                    try:
                        if 'content' in data and 'chapters' in data['content']:
                            for chapter_idx, chapter in enumerate(data['content']['chapters']):
                                chapter_num = chapter_idx + 1

                                # Skip if chapter doesn't match filter
                                if 'chapter_num' in filters and filters['chapter_num'] and chapter_num != filters['chapter_num']:
                                    continue

                                chapter_heading = chapter.get('heading', f"Chapter {chapter_num}")

                                if 'sections' in chapter:
                                    for section_idx, section in enumerate(chapter['sections']):
                                        section_num = section_idx + 1

                                        # Skip if section doesn't match filter
                                        if 'section_num' in filters and filters['section_num'] and section_num != filters['section_num']:
                                            continue

                                        # Get section content and heading
                                        content = section.get('content', '')
                                        heading = section.get('heading', '')
                                        section_text = f"{heading} {content}".lower()

                                        # Calculate relevance score
                                        relevance_score = 0
                                        matched_terms = set()
                                        highlighted_content = content

                                        # Check for exact phrase matches
                                        for phrase in exact_phrases:
                                            if phrase in section_text:
                                                relevance_score += 10  # Higher score for exact phrase matches
                                                matched_terms.add(phrase)

                                                # Create regex for highlighting that preserves case
                                                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                                                highlighted_content = pattern.sub(r'<mark>\g<0></mark>', highlighted_content)

                                        # Check for individual term matches
                                        for term in terms:
                                            if term in section_text:
                                                relevance_score += 5  # Base score for term match
                                                matched_terms.add(term)

                                                # Bonus for term in heading
                                                if term in heading.lower():
                                                    relevance_score += 3

                                                # Create regex for highlighting that preserves case
                                                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
                                                highlighted_content = pattern.sub(r'<mark>\g<0></mark>', highlighted_content)

                                        # Only include results that match at least one term or phrase
                                        if matched_terms:
                                            # Create a snippet around the first match
                                            snippet = create_snippet(content, list(matched_terms)[0], 150)
                                            highlighted_snippet = create_snippet(highlighted_content, list(matched_terms)[0], 150)

                                            matching_sections.append({
                                                'title_num': title_num,
                                                'title_name': title_name,
                                                'chapter_num': chapter_num,
                                                'chapter_heading': chapter_heading,
                                                'section_num': section_num,
                                                'heading': heading,
                                                'snippet': snippet,
                                                'highlighted_snippet': highlighted_snippet,
                                                'relevance_score': relevance_score,
                                                'matched_terms': list(matched_terms)
                                            })
                    except Exception as e:
                        logger.warning(f"Error finding matching sections in {json_file.name}: {e}")
                        logger.debug(f"Traceback: {traceback.format_exc()}")

                    # If we found specific sections, add them to results
                    if matching_sections:
                        results.extend(matching_sections)
                    elif not filters:  # Only add title-level match if no specific filters are applied
                        # Check if title matches any terms
                        title_text = title_name.lower()
                        title_matches = False
                        relevance_score = 0
                        matched_terms = set()

                        # Check for exact phrase matches in title
                        for phrase in exact_phrases:
                            if phrase in title_text:
                                title_matches = True
                                relevance_score += 8  # High score for title match
                                matched_terms.add(phrase)

                        # Check for individual term matches in title
                        for term in terms:
                            if term in title_text:
                                title_matches = True
                                relevance_score += 4
                                matched_terms.add(term)

                        if title_matches:
                            results.append({
                                'title_num': title_num,
                                'title_name': title_name,
                                'heading': title_name,
                                'snippet': f"Title contains the search term(s): {', '.join(matched_terms)}",
                                'highlighted_snippet': f"Title contains the search term(s): {', '.join(['<mark>' + term + '</mark>' for term in matched_terms])}",
                                'relevance_score': relevance_score,
                                'matched_terms': list(matched_terms),
                                'is_title_match': True
                            })
                except Exception as e:
                    logger.error(f"Error searching title {title_num}: {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")

        # Sort results by relevance score (descending)
        results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return results
    except DataLoadError:
        # Re-raise this specific exception to be caught by the caller
        raise
    except Exception as e:
        # Catch any other exceptions and convert to DataLoadError
        logger.error(f"Unexpected error in search_titles: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise DataLoadError(f"Failed to search titles") from e

def create_snippet(text, search_term, max_length=150):
    """Create a snippet of text around the first occurrence of a search term

    Args:
        text (str): The text to create a snippet from
        search_term (str): The search term to find in the text
        max_length (int, optional): The maximum length of the snippet

    Returns:
        str: A snippet of text around the search term
    """
    if not text or not search_term:
        return text[:max_length] + "..." if len(text) > max_length else text

    # Find the position of the search term
    pos = text.lower().find(search_term.lower())
    if pos == -1:
        return text[:max_length] + "..." if len(text) > max_length else text

    # Calculate start and end positions for the snippet
    start = max(0, pos - max_length // 2)
    end = min(len(text), pos + len(search_term) + max_length // 2)

    # Adjust to not break words
    if start > 0:
        # Find the first space before the start position
        space_before = text.rfind(" ", 0, start)
        if space_before != -1:
            start = space_before + 1

    if end < len(text):
        # Find the first space after the end position
        space_after = text.find(" ", end)
        if space_after != -1:
            end = space_after

    # Create the snippet
    snippet = text[start:end]

    # Add ellipsis if needed
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet

@app.route('/')
@cache_control(max_age=3600)  # Cache for 1 hour
def index():
    """Home page"""
    try:
        titles = get_all_titles()
        return render_template('index_modern.html', titles=titles)
    except DataLoadError as e:
        logger.error(f"Error loading titles for index page: {e}")
        return render_template('error_modern.html', message="Error loading titles. Please try again later."), 500

@app.route('/title/<int:title_num>')
@cache_control(max_age=3600)  # Cache for 1 hour
def title(title_num):
    """Title page"""
    try:
        data = load_title_data(title_num)
        if not data:
            return render_template('error_modern.html', message=f"Title {title_num} not found"), 404

        return render_template('title_modern.html', title_num=title_num, data=data)
    except DataLoadError as e:
        logger.error(f"Error loading title {title_num}: {e}")
        return render_template('error_modern.html', message=f"Error loading Title {title_num}. Please try again later."), 500
    except EncodingError as e:
        logger.error(f"Encoding error for title {title_num}: {e}")
        return render_template('error_modern.html', message=f"Encoding error in Title {title_num}. Please try again later."), 500
    except Exception as e:
        logger.error(f"Unexpected error in title route for {title_num}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

@app.route('/chapter/<int:title_num>/<int:chapter_num>')
@cache_control(max_age=3600)  # Cache for 1 hour
def chapter(title_num, chapter_num):
    """Chapter page"""
    try:
        data = load_title_data(title_num)
        if not data:
            return render_template('error_modern.html', message=f"Title {title_num} not found"), 404
    except (DataLoadError, EncodingError) as e:
        logger.error(f"Error loading title {title_num} for chapter view: {e}")
        return render_template('error_modern.html', message=f"Error loading Title {title_num}. Please try again later."), 500
    except Exception as e:
        logger.error(f"Unexpected error loading title {title_num} for chapter view: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

    # Find the chapter
    try:
        chapter_data = None
        for chapter in data['content']['chapters']:
            try:
                # Try to extract chapter number from the chapter num field
                chapter_match = re.search(r'CHAPTER (\d+)', chapter.get('num', ''))
                if chapter_match and chapter_num == int(chapter_match.group(1)):
                    chapter_data = chapter
                    break
            except (AttributeError, ValueError, TypeError) as e:
                # If we can't parse the chapter number, try using the index
                logger.warning(f"Error parsing chapter number in title {title_num}: {e}")
                continue

        # If we didn't find the chapter by number, try using the index
        if not chapter_data and 0 <= chapter_num - 1 < len(data['content']['chapters']):
            chapter_data = data['content']['chapters'][chapter_num - 1]
            logger.info(f"Using index-based lookup for chapter {chapter_num} in title {title_num}")

        if not chapter_data:
            return render_template('error_modern.html', message=f"Chapter {chapter_num} not found in Title {title_num}"), 404

        return render_template('chapter_modern.html', title_num=title_num, chapter_num=chapter_num, chapter_data=chapter_data)
    except Exception as e:
        logger.error(f"Error processing chapter {chapter_num} in title {title_num}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message=f"Error processing Chapter {chapter_num}. Please try again later."), 500

@app.route('/section/<int:title_num>/<int:chapter_num>/<int:section_num>')
@cache_control(max_age=3600)  # Cache for 1 hour
def section(title_num, chapter_num, section_num):
    """Section page"""
    try:
        # Load title data
        try:
            data = load_title_data(title_num)
            if not data:
                return render_template('error_modern.html', message=f"Title {title_num} not found"), 404
        except (DataLoadError, EncodingError) as e:
            logger.error(f"Error loading title {title_num} for section view: {e}")
            return render_template('error_modern.html', message=f"Error loading Title {title_num}. Please try again later."), 500
        except Exception as e:
            logger.error(f"Unexpected error loading title {title_num} for section view: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

        # Find the chapter
        try:
            chapter_data = None
            for chapter in data['content']['chapters']:
                try:
                    # Try to extract chapter number from the chapter num field
                    chapter_match = re.search(r'CHAPTER (\d+)', chapter.get('num', ''))
                    if chapter_match and chapter_num == int(chapter_match.group(1)):
                        chapter_data = chapter
                        break
                except (AttributeError, ValueError, TypeError):
                    continue

            # If we didn't find the chapter by number, try using the index
            if not chapter_data and 0 <= chapter_num - 1 < len(data['content']['chapters']):
                chapter_data = data['content']['chapters'][chapter_num - 1]
                logger.info(f"Using index-based lookup for chapter {chapter_num} in title {title_num}")

            if not chapter_data:
                return render_template('error_modern.html', message=f"Chapter {chapter_num} not found in Title {title_num}"), 404
        except Exception as e:
            logger.error(f"Error finding chapter {chapter_num} in title {title_num}: {e}")
            return render_template('error_modern.html', message=f"Error processing Chapter {chapter_num}. Please try again later."), 500

        # Find the section
        try:
            section_data = None
            for section in chapter_data.get('sections', []):
                try:
                    # Try to extract section number from the section num field
                    section_match = re.search(r'\u00a7\s*(\d+)', section.get('num', ''))
                    if section_match and section_num == int(section_match.group(1)):
                        section_data = section
                        break
                except (AttributeError, ValueError, TypeError):
                    continue

            # If we didn't find the section by number, try using the index
            if not section_data and 0 <= section_num - 1 < len(chapter_data.get('sections', [])):
                section_data = chapter_data['sections'][section_num - 1]
                logger.info(f"Using index-based lookup for section {section_num} in chapter {chapter_num} of title {title_num}")

            if not section_data:
                return render_template('error_modern.html', message=f"Section {section_num} not found in Chapter {chapter_num} of Title {title_num}"), 404

            return render_template('section_modern.html', title_num=title_num, chapter_num=chapter_num, section_num=section_num, section_data=section_data)
        except Exception as e:
            logger.error(f"Error finding section {section_num} in chapter {chapter_num} of title {title_num}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return render_template('error_modern.html', message=f"Error processing Section {section_num}. Please try again later."), 500
    except Exception as e:
        logger.error(f"Unexpected error in section route: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

@app.route('/search')
@cache_control(max_age=300)  # Cache for 5 minutes (shorter for search results)
def search():
    """Search page"""
    try:
        # Get search parameters
        query = request.args.get('q', '')
        title_filter = request.args.get('title', '')
        chapter_filter = request.args.get('chapter', '')
        section_filter = request.args.get('section', '')
        sort_by = request.args.get('sort', 'relevance')  # Default sort by relevance

        if not query:
            return render_template('search_modern.html', query='', results=[])

        # Build filters
        filters = {}
        if title_filter and title_filter.isdigit():
            filters['title_num'] = int(title_filter)
        if chapter_filter and chapter_filter.isdigit():
            filters['chapter_num'] = int(chapter_filter)
        if section_filter and section_filter.isdigit():
            filters['section_num'] = int(section_filter)

        try:
            # Get all titles for the filter dropdown
            all_titles = get_all_titles()

            # Perform the search
            results = search_titles(query, filters)

            # Apply sorting if needed
            if sort_by == 'title':
                results.sort(key=lambda x: x.get('title_num', 0))
            elif sort_by == 'chapter':
                results.sort(key=lambda x: (x.get('title_num', 0), x.get('chapter_num', 0)))
            elif sort_by == 'section':
                results.sort(key=lambda x: (x.get('title_num', 0), x.get('chapter_num', 0), x.get('section_num', 0)))
            # Default is already sorted by relevance

            # Get statistics for the search results
            stats = {
                'total_results': len(results),
                'title_matches': sum(1 for r in results if r.get('is_title_match', False)),
                'section_matches': sum(1 for r in results if not r.get('is_title_match', False)),
                'titles_found': len(set(r.get('title_num', 0) for r in results)),
                'chapters_found': len(set((r.get('title_num', 0), r.get('chapter_num', 0)) for r in results if 'chapter_num' in r)),
            }

            return render_template(
                'search_modern.html',
                query=query,
                results=results,
                stats=stats,
                all_titles=all_titles,
                filters={
                    'title': title_filter,
                    'chapter': chapter_filter,
                    'section': section_filter,
                    'sort': sort_by
                }
            )
        except DataLoadError as e:
            logger.error(f"Error searching titles: {e}")
            return render_template('error_modern.html', message="Error searching titles. Please try again later."), 500
        except Exception as e:
            logger.error(f"Unexpected error in search: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return render_template('error_modern.html', message="An unexpected error occurred during search. Please try again later."), 500
    except Exception as e:
        logger.error(f"Unexpected error in search route: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

# API endpoint for search suggestions
@app.route('/api/search/suggestions')
@cache_control(max_age=300)  # Cache for 5 minutes
def api_search_suggestions():
    """API endpoint to get search suggestions"""
    try:
        query = request.args.get('q', '').lower().strip()
        if not query or len(query) < 2:  # Require at least 2 characters
            return jsonify({'suggestions': []})

        # Get all titles
        all_titles = get_all_titles()

        # Find matching titles
        title_suggestions = []
        for title in all_titles:
            title_name = title.get('name', '').lower()
            if query in title_name:
                title_suggestions.append({
                    'type': 'title',
                    'title_num': title.get('number'),
                    'text': f"Title {title.get('number')}: {title.get('name')}"
                })

        # Limit to top 5 title suggestions
        title_suggestions = title_suggestions[:5]

        # If we have a specific title in the query, try to find matching chapters and sections
        chapter_suggestions = []
        section_suggestions = []

        # Look for title number pattern in query (e.g., "title 5" or "t5")
        title_match = re.search(r'(?:title|t)[\s]*?(\d+)', query)
        if title_match:
            title_num = int(title_match.group(1))

            # Load the title data
            title_data = load_title_data(title_num)
            if title_data and 'content' in title_data and 'chapters' in title_data['content']:
                # Find matching chapters
                for chapter_idx, chapter in enumerate(title_data['content']['chapters']):
                    chapter_num = chapter_idx + 1
                    chapter_heading = chapter.get('heading', '').lower()

                    # Remove the title number from the query for better matching
                    clean_query = query.replace(title_match.group(0), '').strip()

                    if clean_query and clean_query in chapter_heading:
                        chapter_suggestions.append({
                            'type': 'chapter',
                            'title_num': title_num,
                            'chapter_num': chapter_num,
                            'text': f"Title {title_num}, Chapter {chapter_num}: {chapter.get('heading')}"
                        })

                    # Find matching sections if we have a chapter match
                    if 'sections' in chapter:
                        for section_idx, section in enumerate(chapter['sections']):
                            section_num = section_idx + 1
                            section_heading = section.get('heading', '').lower()

                            if clean_query and clean_query in section_heading:
                                section_suggestions.append({
                                    'type': 'section',
                                    'title_num': title_num,
                                    'chapter_num': chapter_num,
                                    'section_num': section_num,
                                    'text': f"Title {title_num}, Chapter {chapter_num}, Section {section_num}: {section.get('heading')}"
                                })

        # Limit suggestions
        chapter_suggestions = chapter_suggestions[:3]
        section_suggestions = section_suggestions[:5]

        # Combine all suggestions
        all_suggestions = title_suggestions + chapter_suggestions + section_suggestions

        # Add a generic search suggestion
        if query:
            all_suggestions.append({
                'type': 'search',
                'text': f"Search for '{query}' in all titles"
            })

        return jsonify({'suggestions': all_suggestions})
    except Exception as e:
        logger.error(f"Error in search suggestions API: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': "An error occurred while getting search suggestions"}), 500

# API endpoints for lazy loading
@app.route('/api/title/<int:title_num>/chapters')
@cache_control(max_age=3600)  # Cache for 1 hour
def api_title_chapters(title_num):
    """API endpoint to get chapters for a title"""
    try:
        data = load_title_data(title_num)
        if not data or 'content' not in data or 'chapters' not in data['content']:
            return jsonify({'error': f"Title {title_num} not found or has no chapters"}), 404

        # Extract just the chapter data we need
        chapters = []
        for idx, chapter in enumerate(data['content']['chapters']):
            chapters.append({
                'num': idx + 1,  # Use index as chapter number for simplicity
                'heading': chapter.get('heading', f"Chapter {idx + 1}"),
                'display_num': chapter.get('num', f"Chapter {idx + 1}")
            })

        return jsonify({'chapters': chapters})
    except Exception as e:
        logger.error(f"Error in API endpoint for title {title_num} chapters: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': "An unexpected error occurred"}), 500

@app.route('/api/title/<int:title_num>/chapter/<int:chapter_num>/sections')
@cache_control(max_age=3600)  # Cache for 1 hour
def api_chapter_sections(title_num, chapter_num):
    """API endpoint to get sections for a chapter"""
    try:
        data = load_title_data(title_num)
        if not data or 'content' not in data or 'chapters' not in data['content']:
            return jsonify({'error': f"Title {title_num} not found"}), 404

        # Find the chapter
        chapter_data = None
        if 0 <= chapter_num - 1 < len(data['content']['chapters']):
            chapter_data = data['content']['chapters'][chapter_num - 1]

        if not chapter_data or 'sections' not in chapter_data:
            return jsonify({'error': f"Chapter {chapter_num} not found in Title {title_num} or has no sections"}), 404

        # Extract just the section data we need
        sections = []
        for idx, section in enumerate(chapter_data['sections']):
            sections.append({
                'num': idx + 1,  # Use index as section number for simplicity
                'heading': section.get('heading', f"Section {idx + 1}"),
                'display_num': section.get('num', f"Section {idx + 1}")
            })

        return jsonify({'sections': sections})
    except Exception as e:
        logger.error(f"Error in API endpoint for chapter {chapter_num} sections in title {title_num}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': "An unexpected error occurred"}), 500

@app.route('/updates')
@cache_control(max_age=3600)  # Cache for 1 hour
def updates():
    """Updates page"""
    try:
        # Get current release info
        current_release = update_tracker.get_latest_saved_release()
        if not current_release:
            current_release = {
                'public_law': 'Unknown',
                'date': 'Unknown'
            }

        # Calculate next update date (30 days from now)
        next_update_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

        # Get update history
        updates_list = []
        try:
            # Get all changelog files
            changes_dir = Path("update_data/changes")
            if changes_dir.exists():
                changelog_files = list(changes_dir.glob("changelog_*.json"))

                # Sort by modification time (newest first)
                changelog_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                # Load the changelogs
                for file in changelog_files[:5]:  # Show only the 5 most recent updates
                    try:
                        with open(file, 'r') as f:
                            changelog = json.load(f)
                            updates_list.append(changelog)
                    except Exception as e:
                        logger.error(f"Error loading changelog file {file}: {e}")
        except Exception as e:
            logger.error(f"Error getting update history: {e}")

        # Get status message from session if available
        status_message = session.pop('status_message', None) if hasattr(request, 'session') else None
        status_success = session.pop('status_success', False) if hasattr(request, 'session') else False

        return render_template(
            'updates.html',
            current_release=current_release,
            next_update_date=next_update_date,
            updates=updates_list,
            status_message=status_message,
            status_success=status_success
        )
    except Exception as e:
        logger.error(f"Error in updates route: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

@app.route('/diff/<int:title_num>')
@cache_control(max_age=3600)  # Cache for 1 hour
def diff_view(title_num):
    """Diff visualization page"""
    try:
        # Get version parameters
        old_version = request.args.get('old', 'current')
        new_version = request.args.get('new', 'current')
        view_mode = request.args.get('view', 'inline')

        # Get available versions
        available_versions = diff_visualizer.get_available_versions(title_num)

        # If no versions available, show error
        if not available_versions:
            return render_template('error_modern.html', message=f"No versions available for Title {title_num}"), 404

        # If versions are specified, generate diff
        diff_data = None
        diff_summary = None

        if old_version != new_version and old_version in available_versions and new_version in available_versions:
            # Compare the versions
            diff_data = diff_visualizer.compare_title_versions(title_num, old_version, new_version)

            if diff_data:
                # Generate HTML for each section diff
                for chapter in diff_data.get('chapter_diffs', []):
                    for section in chapter.get('section_diffs', []):
                        # Generate HTML for content diff
                        if section.get('content_diff'):
                            section['content_diff_html'] = diff_visualizer.generate_html_diff(
                                section['content_diff'],
                                inline=(view_mode == 'inline')
                            )

                        # Generate HTML for subsection diffs
                        for subsection in section.get('subsection_diffs', []):
                            if subsection.get('diff'):
                                subsection['diff_html'] = diff_visualizer.generate_html_diff(
                                    subsection['diff'],
                                    inline=(view_mode == 'inline')
                                )

                # Generate summary statistics
                added_sections = 0
                deleted_sections = 0
                modified_sections = 0

                for chapter in diff_data.get('chapter_diffs', []):
                    for section in chapter.get('section_diffs', []):
                        if section.get('status') == 'added':
                            added_sections += 1
                        elif section.get('status') == 'deleted':
                            deleted_sections += 1
                        elif section.get('status') == 'modified':
                            modified_sections += 1

                diff_summary = {
                    'added_sections': added_sections,
                    'deleted_sections': deleted_sections,
                    'modified_sections': modified_sections,
                    'total_changes': added_sections + deleted_sections + modified_sections
                }

        return render_template(
            'diff_view.html',
            title_num=title_num,
            old_version=old_version,
            new_version=new_version,
            view_mode=view_mode,
            available_versions=available_versions,
            diff_data=diff_data,
            diff_summary=diff_summary
        )
    except Exception as e:
        logger.error(f"Error in diff_view route: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return render_template('error_modern.html', message="An unexpected error occurred. Please try again later."), 500

@app.route('/subscribe-updates', methods=['POST'])
def subscribe_updates():
    """Subscribe to updates"""
    try:
        email = request.form.get('email', '').strip()
        titles = request.form.getlist('titles')

        if not email or '@' not in email:
            flash("Please enter a valid email address", "error")
            return redirect(url_for('updates'))

        # Convert titles to integers if provided
        title_numbers = None
        if titles:
            try:
                title_numbers = [int(t) for t in titles]
            except ValueError:
                flash("Invalid title numbers provided", "error")
                return redirect(url_for('updates'))

        # Subscribe to updates
        success = update_tracker.subscribe_to_updates(email, title_numbers)

        if success:
            if hasattr(request, 'session'):
                session['status_message'] = f"Successfully subscribed {email} to updates"
                session['status_success'] = True
        else:
            if hasattr(request, 'session'):
                session['status_message'] = f"Failed to subscribe {email} to updates"
                session['status_success'] = False

        return redirect(url_for('updates'))
    except Exception as e:
        logger.error(f"Error in subscribe_updates route: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        if hasattr(request, 'session'):
            session['status_message'] = "An unexpected error occurred"
            session['status_success'] = False
        return redirect(url_for('updates'))

@app.route('/api/webhooks', methods=['GET', 'POST'])
def api_webhooks():
    """API endpoint for webhook management"""
    try:
        if request.method == 'GET':
            # List webhooks
            webhooks = webhook_manager.list_webhooks()
            return jsonify({
                'webhooks': webhooks,
                'count': len(webhooks)
            })
        elif request.method == 'POST':
            # Register a new webhook
            data = request.json

            if not data or 'url' not in data:
                return jsonify({'error': 'URL is required'}), 400

            url = data.get('url')
            description = data.get('description')
            events = data.get('events')
            secret = data.get('secret')
            format = data.get('format', 'json')
            headers = data.get('headers')

            webhook_id = webhook_manager.register_webhook(
                url=url,
                description=description,
                events=events,
                secret=secret,
                format=format,
                headers=headers
            )

            if webhook_id:
                return jsonify({
                    'id': webhook_id,
                    'message': 'Webhook registered successfully'
                }), 201
            else:
                return jsonify({'error': 'Failed to register webhook'}), 500
    except Exception as e:
        logger.error(f"Error in webhook API: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/webhooks/<webhook_id>', methods=['GET', 'PUT', 'DELETE'])
def api_webhook(webhook_id):
    """API endpoint for individual webhook management"""
    try:
        if request.method == 'GET':
            # Get webhook details
            webhook = webhook_manager.get_webhook(webhook_id)

            if webhook:
                return jsonify(webhook)
            else:
                return jsonify({'error': 'Webhook not found'}), 404

        elif request.method == 'PUT':
            # Update webhook
            data = request.json

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Extract fields to update
            update_fields = {}
            for field in ['url', 'description', 'events', 'secret', 'format', 'headers', 'active']:
                if field in data:
                    update_fields[field] = data[field]

            success = webhook_manager.update_webhook(webhook_id, **update_fields)

            if success:
                return jsonify({'message': 'Webhook updated successfully'})
            else:
                return jsonify({'error': 'Failed to update webhook'}), 500

        elif request.method == 'DELETE':
            # Delete webhook
            success = webhook_manager.delete_webhook(webhook_id)

            if success:
                return jsonify({'message': 'Webhook deleted successfully'})
            else:
                return jsonify({'error': 'Failed to delete webhook'}), 500

    except Exception as e:
        logger.error(f"Error in webhook API: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/webhooks/test', methods=['POST'])
def api_test_webhook():
    """API endpoint to test webhooks"""
    try:
        data = request.json
        webhook_ids = data.get('webhook_ids') if data and 'webhook_ids' in data else None

        # Create a test payload
        payload = {
            'event': 'test.event',
            'timestamp': datetime.now().isoformat(),
            'message': 'This is a test webhook event',
            'data': {
                'test': True,
                'source': 'US Code Browser API'
            }
        }

        # Trigger the webhooks
        count = webhook_manager.trigger_webhooks('test.event', payload, webhook_ids)

        return jsonify({
            'message': f'Triggered {count} webhooks',
            'count': count
        })

    except Exception as e:
        logger.error(f"Error in webhook test API: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
