# Enhanced Search Capabilities Documentation

This document outlines the enhanced search capabilities implemented in the US Code Browser application.

## Overview

The following search enhancements have been implemented:

1. **Improved search algorithm** - Better relevance ranking and exact phrase matching
2. **Search highlighting** - Highlighting of search terms in results
3. **Advanced search filters** - Filtering by title, chapter, section, and sorting options
4. **Search suggestions/autocomplete** - Real-time suggestions as users type
5. **Enhanced search results page** - Better organization and display of search results

## Improved Search Algorithm

### Features

- **Relevance ranking** - Results are scored based on multiple factors:
  - Exact phrase matches (higher score)
  - Term matches in headings (higher score)
  - Term matches in content (base score)
  - Title matches (special handling)
- **Exact phrase matching** - Support for quoted phrases (e.g., "due process")
- **Context-aware snippets** - Snippets show the search terms in context
- **Term highlighting** - Search terms are highlighted in the results

### Implementation

The search algorithm has been completely rewritten to provide better relevance ranking:

```python
def search_titles(query, filters=None, use_cache=True):
    # Normalize the query
    query = query.lower().strip()
    
    # Parse the query for exact phrases (in quotes)
    exact_phrases = []
    query_without_quotes = query
    for match in re.finditer(r'"([^"]+)"', query):
        exact_phrase = match.group(1).lower()
        exact_phrases.append(exact_phrase)
        query_without_quotes = query_without_quotes.replace(f'"{exact_phrase}"', '')
        
    # Get individual terms (excluding exact phrases)
    terms = [term.strip() for term in query_without_quotes.split() if term.strip()]
    
    # Calculate relevance score for each result
    relevance_score = 0
    
    # Check for exact phrase matches (higher score)
    for phrase in exact_phrases:
        if phrase in section_text:
            relevance_score += 10
            
    # Check for term matches in heading (higher score)
    if term in heading.lower():
        relevance_score += 3
```

## Search Highlighting

### Features

- **Term highlighting** - Search terms are highlighted in the results
- **Case-preserving** - Highlighting preserves the original case of the text
- **Exact phrase highlighting** - Exact phrases are highlighted as a unit

### Implementation

Highlighting is implemented using regular expressions to preserve the original case:

```python
# Create regex for highlighting that preserves case
pattern = re.compile(re.escape(term), re.IGNORECASE)
highlighted_content = pattern.sub(r'<mark>\g<0></mark>', highlighted_content)
```

The highlighted content is then passed to the template and displayed using the `safe` filter to render the HTML:

```html
<p class="snippet">{{ result.highlighted_snippet|safe }}</p>
```

## Advanced Search Filters

### Features

- **Title filter** - Filter results by title number
- **Chapter filter** - Filter results by chapter number
- **Section filter** - Filter results by section number
- **Sort options** - Sort by relevance, title, chapter, or section
- **Filter display** - Active filters are displayed with remove options
- **Clear all** - Option to clear all filters at once

### Implementation

Filters are implemented as query parameters in the search route:

```python
# Get search parameters
query = request.args.get('q', '')
title_filter = request.args.get('title', '')
chapter_filter = request.args.get('chapter', '')
section_filter = request.args.get('section', '')
sort_by = request.args.get('sort', 'relevance')  # Default sort by relevance

# Build filters
filters = {}
if title_filter and title_filter.isdigit():
    filters['title_num'] = int(title_filter)
if chapter_filter and chapter_filter.isdigit():
    filters['chapter_num'] = int(chapter_filter)
if section_filter and section_filter.isdigit():
    filters['section_num'] = int(section_filter)
```

The filters are then passed to the search function and applied to the results:

```python
# Skip if title doesn't match filter
if 'title_num' in filters and filters['title_num'] and title_num != filters['title_num']:
    continue
```

## Search Suggestions/Autocomplete

### Features

- **Real-time suggestions** - Suggestions appear as the user types
- **Multiple suggestion types** - Title, chapter, section, and generic search suggestions
- **Type indicators** - Visual indicators for different suggestion types
- **Keyboard navigation** - Arrow keys to navigate suggestions
- **Debouncing** - Prevents excessive API calls while typing

### Implementation

A new API endpoint provides search suggestions:

```python
@app.route('/api/search/suggestions')
@cache_control(max_age=300)  # Cache for 5 minutes
def api_search_suggestions():
    query = request.args.get('q', '').lower().strip()
    if not query or len(query) < 2:  # Require at least 2 characters
        return jsonify({'suggestions': []})
        
    # Find matching titles, chapters, and sections
    # ...
    
    return jsonify({'suggestions': all_suggestions})
```

The frontend uses JavaScript to fetch and display suggestions:

```javascript
function fetchSuggestions(query) {
    fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.suggestions && data.suggestions.length > 0) {
                renderSuggestions(data.suggestions);
                suggestionsContainer.style.display = 'block';
            } else {
                suggestionsContainer.style.display = 'none';
            }
        });
}
```

## Enhanced Search Results Page

### Features

- **Search statistics** - Shows the number of results, titles, and chapters found
- **Active filters display** - Shows which filters are currently active
- **Relevance indicators** - Visual indicators of result relevance
- **Result type indicators** - Indicates whether a result is a title or section match
- **Matched terms display** - Shows which terms matched in each result
- **Improved no results page** - Provides search tips when no results are found

### Implementation

The search results page has been completely redesigned with new HTML and CSS:

```html
<div class="search-stats">
    <p>Found {{ stats.total_results }} results across {{ stats.titles_found }} titles and {{ stats.chapters_found }} chapters</p>
</div>

<div class="search-result-meta">
    {% if result.is_title_match is defined and result.is_title_match %}
        <span class="result-type">Title Match</span>
    {% else %}
        <span class="result-type">Section Match</span>
    {% endif %}
    
    <span class="relevance">
        Relevance: 
        <span class="relevance-score">
            <span class="relevance-score-fill" style="width: {{ (result.relevance_score / 20) * 100 }}%"></span>
        </span>
    </span>
</div>
```

## Usage Examples

### Basic Search

To perform a basic search, simply enter a query in the search box:

```
congress
```

### Exact Phrase Search

To search for an exact phrase, enclose it in quotes:

```
"due process"
```

### Advanced Search

To use advanced search options:

1. Click on "Advanced Search Options"
2. Select a title from the dropdown
3. Enter a chapter number (optional)
4. Enter a section number (optional)
5. Select a sort option (optional)
6. Click "Search"

### Using Search Suggestions

As you type in the search box, suggestions will appear:

1. Title suggestions - Click to go directly to that title
2. Chapter suggestions - Click to go directly to that chapter
3. Section suggestions - Click to go directly to that section
4. Generic search - Click to search for the current query

## Future Enhancements

Additional search enhancements that could be implemented in the future:

1. **Full-text search engine** - Implement a proper search engine like Elasticsearch
2. **Fuzzy matching** - Support for typos and similar terms
3. **Boolean operators** - Support for AND, OR, NOT operators
4. **Field-specific search** - Search only in headings, content, etc.
5. **Search history** - Save recent searches
6. **Saved searches** - Allow users to save and name searches
7. **Search analytics** - Track popular search terms
8. **Related searches** - Suggest related search terms
