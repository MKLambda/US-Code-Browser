# Performance Optimizations Documentation

This document outlines the performance optimizations implemented in the US Code Browser application.

## Overview

The following performance optimizations have been implemented:

1. **Server-side caching** - Caching title data in memory to reduce JSON parsing overhead
2. **Lazy loading** - Loading chapters and sections on demand rather than loading entire titles at once
3. **Compression** - Implementing gzip compression for API responses
4. **Cache control headers** - Adding cache control headers to responses for browser caching

## Server-side Caching

### Implementation

Server-side caching has been implemented using in-memory dictionaries to store title data and the list of all titles.

```python
# Cache settings
CACHE_TIMEOUT = 3600  # Cache timeout in seconds (1 hour)
CACHE_ENABLED = True  # Enable/disable caching

# In-memory cache for title data
title_cache = {}
# In-memory cache for all titles list
all_titles_cache = {'data': None, 'timestamp': 0}
```

The `load_title_data` and `get_all_titles` functions have been modified to check the cache before loading data from disk:

```python
def load_title_data(title_num, use_cache=True):
    # Check cache first if enabled
    if CACHE_ENABLED and use_cache and title_num in title_cache:
        cache_entry = title_cache[title_num]
        # Check if cache entry is still valid
        if time.time() - cache_entry['timestamp'] < CACHE_TIMEOUT:
            logger.debug(f"Using cached data for title {title_num}")
            return cache_entry['data']
        else:
            logger.debug(f"Cache expired for title {title_num}")
    
    # Load data from disk if not in cache or cache expired
    # ...
    
    # Cache the data if caching is enabled
    if CACHE_ENABLED:
        title_cache[title_num] = {
            'data': data,
            'timestamp': time.time()
        }
        logger.debug(f"Cached data for title {title_num}")
```

### Benefits

- Reduces disk I/O operations
- Eliminates repeated JSON parsing
- Significantly improves response times for frequently accessed titles
- Reduces server load

## Lazy Loading

### Implementation

Lazy loading has been implemented for chapters and sections using AJAX requests to load data on demand.

New API endpoints have been added to fetch chapters and sections:

```python
@app.route('/api/title/<int:title_num>/chapters')
@cache_control(max_age=3600)  # Cache for 1 hour
def api_title_chapters(title_num):
    """API endpoint to get chapters for a title"""
    # ...

@app.route('/api/title/<int:title_num>/chapter/<int:chapter_num>/sections')
@cache_control(max_age=3600)  # Cache for 1 hour
def api_chapter_sections(title_num, chapter_num):
    """API endpoint to get sections for a chapter"""
    # ...
```

The templates have been updated to use JavaScript to fetch and display chapters and sections:

```javascript
// Fetch chapters data
fetch('/api/title/{{ title_num }}/chapters')
    .then(response => response.json())
    .then(data => {
        // Create chapter items
        // ...
    });
```

### Benefits

- Reduces initial page load time
- Reduces memory usage on both server and client
- Improves perceived performance
- Allows for more responsive UI

## Compression

### Implementation

Gzip compression has been implemented for API responses using a Flask after_request handler:

```python
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
```

### Benefits

- Reduces bandwidth usage
- Improves page load times
- Reduces server egress costs
- Improves user experience on slow connections

## Cache Control Headers

### Implementation

Cache control headers have been added to responses using a decorator:

```python
def cache_control(max_age=CACHE_TIMEOUT):
    """Decorator to add cache control headers to responses"""
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
```

The decorator has been applied to all routes:

```python
@app.route('/')
@cache_control(max_age=3600)  # Cache for 1 hour
def index():
    # ...
```

### Benefits

- Enables browser caching
- Reduces server load for repeated requests
- Improves page load times for returning visitors
- Reduces bandwidth usage

## Performance Metrics

### Before Optimizations

- Average page load time: [Baseline metrics would go here]
- Server memory usage: [Baseline metrics would go here]
- Bandwidth usage: [Baseline metrics would go here]

### After Optimizations

- Average page load time: [Improved metrics would go here]
- Server memory usage: [Improved metrics would go here]
- Bandwidth usage: [Improved metrics would go here]

## Future Optimizations

Additional performance optimizations that could be implemented in the future:

1. **Database storage** - Replace JSON files with a proper database for better query performance
2. **Content Delivery Network (CDN)** - Use a CDN for static assets
3. **Pagination** - Add pagination for large lists of chapters and sections
4. **Image optimization** - Optimize any images used in the UI
5. **Resource hints** - Add preload/prefetch directives for critical resources
6. **Service Worker** - Implement a service worker for offline support and better caching
7. **Code splitting** - Split JavaScript into smaller chunks loaded only when needed

## Configuration

The performance optimizations can be configured using the following settings:

```python
# Cache settings
CACHE_TIMEOUT = 3600  # Cache timeout in seconds (1 hour)
CACHE_ENABLED = True  # Enable/disable caching

# Compression threshold in bytes
COMPRESSION_THRESHOLD = 1024  # Only compress responses larger than 1KB
```

These settings can be adjusted based on server resources and performance requirements.
