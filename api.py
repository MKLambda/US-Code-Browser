from flask import Flask, request, jsonify
from flask_restful import Api, Resource
import json
from pathlib import Path
import re
import logging

app = Flask(__name__)
api = Api(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api.log')
    ]
)

logger = logging.getLogger('api')

def load_title_data(title_num):
    """Load data for a specific title"""
    title_str = str(title_num).zfill(2)
    processed_dir = Path("processed")

    # Find the JSON file for this title
    json_files = list(processed_dir.glob(f"usc{title_str}.json"))
    if not json_files:
        return None

    # Load the JSON data
    try:
        with open(json_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except UnicodeDecodeError:
        # Try with different encodings if UTF-8 fails
        try:
            with open(json_files[0], 'r', encoding='latin-1') as f:
                data = json.load(f)
            logger.warning(f"Loaded title {title_num} with latin-1 encoding")
            return data
        except Exception as e2:
            logger.error(f"Error loading title {title_num} with alternative encoding: {e2}")
            return None
    except Exception as e:
        logger.error(f"Error loading title {title_num}: {e}")
        return None

def get_all_titles():
    """Get a list of all available titles"""
    processed_dir = Path("processed")

    # Get all JSON files in the processed directory
    json_files = list(processed_dir.glob("*.json"))

    # Extract title numbers and names
    titles = []
    for json_file in json_files:
        match = re.search(r'usc(\d+)\.json', json_file.name)
        if match:
            title_num = int(match.group(1))

            # Load the title data to get the name
            try:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except UnicodeDecodeError:
                    # Try with different encodings if UTF-8 fails
                    with open(json_file, 'r', encoding='latin-1') as f:
                        data = json.load(f)
                    logger.warning(f"Loaded title list with latin-1 encoding for {json_file.name}")

                title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"

                titles.append({
                    'number': title_num,
                    'name': title_name
                })
            except Exception as e:
                logger.error(f"Error loading title {title_num}: {e}")

    # Sort titles by number
    titles.sort(key=lambda x: x['number'])

    return titles

def search_titles(query):
    """Search all titles for a specific query"""
    processed_dir = Path("processed")

    # Get all JSON files in the processed directory
    json_files = list(processed_dir.glob("*.json"))

    # Search each file for the query
    results = []
    for json_file in json_files:
        match = re.search(r'usc(\d+)\.json', json_file.name)
        if match:
            title_num = int(match.group(1))

            # Load the title data
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Convert the data to a string for simple searching
                data_str = json.dumps(data)

                # Check if the query is in the data
                if query.lower() in data_str.lower():
                    title_name = data['content']['title']['heading'] if 'content' in data and 'title' in data['content'] and 'heading' in data['content']['title'] else f"Title {title_num}"

                    results.append({
                        'number': title_num,
                        'name': title_name
                    })
            except Exception as e:
                logger.error(f"Error searching title {title_num}: {e}")

    # Sort results by title number
    results.sort(key=lambda x: x['number'])

    return results

class TitleList(Resource):
    def get(self):
        """Get a list of all titles"""
        titles = get_all_titles()
        return jsonify(titles)

class Title(Resource):
    def get(self, title_num):
        """Get data for a specific title"""
        data = load_title_data(title_num)
        if not data:
            return {"error": f"Title {title_num} not found"}, 404

        return jsonify(data)

class Chapter(Resource):
    def get(self, title_num, chapter_num):
        """Get data for a specific chapter"""
        data = load_title_data(title_num)
        if not data:
            return {"error": f"Title {title_num} not found"}, 404

        # Find the chapter
        chapter_data = None
        for chapter in data['content']['chapters']:
            try:
                chapter_number = int(re.search(r'CHAPTER (\d+)', chapter['num']).group(1))
                if chapter_number == chapter_num:
                    chapter_data = chapter
                    break
            except:
                continue

        if not chapter_data:
            return {"error": f"Chapter {chapter_num} not found in Title {title_num}"}, 404

        return jsonify(chapter_data)

class Section(Resource):
    def get(self, title_num, chapter_num, section_num):
        """Get data for a specific section"""
        data = load_title_data(title_num)
        if not data:
            return {"error": f"Title {title_num} not found"}, 404

        # Find the chapter
        chapter_data = None
        for chapter in data['content']['chapters']:
            try:
                chapter_number = int(re.search(r'CHAPTER (\d+)', chapter['num']).group(1))
                if chapter_number == chapter_num:
                    chapter_data = chapter
                    break
            except:
                continue

        if not chapter_data:
            return {"error": f"Chapter {chapter_num} not found in Title {title_num}"}, 404

        # Find the section
        section_data = None
        for section in chapter_data['sections']:
            try:
                section_number = int(re.search(r'§\s*(\d+)', section['num']).group(1))
                if section_number == section_num:
                    section_data = section
                    break
            except:
                continue

        if not section_data:
            return {"error": f"Section {section_num} not found in Chapter {chapter_num} of Title {title_num}"}, 404

        return jsonify(section_data)

class Search(Resource):
    def get(self):
        """Search all titles for a specific query"""
        query = request.args.get('q', '')
        if not query:
            return {"error": "No query provided"}, 400

        results = search_titles(query)
        return jsonify(results)

# Add resources to the API
api.add_resource(TitleList, '/api/titles')
api.add_resource(Title, '/api/titles/<int:title_num>')
api.add_resource(Chapter, '/api/titles/<int:title_num>/chapters/<int:chapter_num>')
api.add_resource(Section, '/api/titles/<int:title_num>/chapters/<int:chapter_num>/sections/<int:section_num>')
api.add_resource(Search, '/api/search')

@app.route('/')
def index():
    """API documentation"""
    return jsonify({
        "name": "US Laws API",
        "version": "1.0.0",
        "description": "API for accessing the United States Code",
        "endpoints": [
            {
                "path": "/api/titles",
                "method": "GET",
                "description": "Get a list of all titles"
            },
            {
                "path": "/api/titles/<title_num>",
                "method": "GET",
                "description": "Get data for a specific title"
            },
            {
                "path": "/api/titles/<title_num>/chapters/<chapter_num>",
                "method": "GET",
                "description": "Get data for a specific chapter"
            },
            {
                "path": "/api/titles/<title_num>/chapters/<chapter_num>/sections/<section_num>",
                "method": "GET",
                "description": "Get data for a specific section"
            },
            {
                "path": "/api/search?q=<query>",
                "method": "GET",
                "description": "Search all titles for a specific query"
            }
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
