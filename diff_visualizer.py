"""
US Code Diff Visualizer

This module provides diff visualization for the US Code Browser, allowing:
- Comparison between different versions of the US Code
- Visual highlighting of changes (additions, deletions, modifications)
- Side-by-side and inline diff views
- HTML and JSON output formats
"""

import json
import logging
import difflib
import re
from pathlib import Path
from datetime import datetime
import html

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'diff_visualizer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger('diff_visualizer')

class DiffVisualizer:
    """Visualizes differences between versions of the US Code"""
    
    def __init__(self, data_dir="diff_data"):
        """Initialize the diff visualizer
        
        Args:
            data_dir (str): Directory to store diff data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from config file"""
        config_file = self.data_dir / "diff_config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading diff config: {e}")
        
        # Default configuration
        default_config = {
            "visualization": {
                "context_lines": 3,
                "line_length": 80,
                "word_diff": True
            },
            "cache": {
                "enabled": True,
                "max_age_days": 30
            },
            "html": {
                "addition_class": "diff-add",
                "deletion_class": "diff-del",
                "context_class": "diff-ctx",
                "line_numbers": True
            }
        }
        
        # Save default configuration
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def save_config(self):
        """Save configuration to config file"""
        config_file = self.data_dir / "diff_config.json"
        
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Diff configuration saved")
        except Exception as e:
            logger.error(f"Error saving diff config: {e}")
    
    def compare_text(self, old_text, new_text, context_lines=None, word_diff=None):
        """Compare two text strings and return a diff
        
        Args:
            old_text (str): The old text
            new_text (str): The new text
            context_lines (int, optional): Number of context lines
            word_diff (bool, optional): Whether to perform word-level diffing
            
        Returns:
            list: List of diff blocks
        """
        if context_lines is None:
            context_lines = self.config['visualization']['context_lines']
        
        if word_diff is None:
            word_diff = self.config['visualization']['word_diff']
        
        # Split text into lines
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            old_lines,
            new_lines,
            n=context_lines,
            lineterm=''
        ))
        
        # Process the diff into blocks
        blocks = []
        current_block = None
        
        for line in diff:
            # Skip the header lines
            if line.startswith('---') or line.startswith('+++'):
                continue
            
            # Handle chunk headers
            if line.startswith('@@'):
                # If we have a current block, add it to the list
                if current_block:
                    blocks.append(current_block)
                
                # Parse the chunk header
                match = re.match(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2) or 1)
                    new_start = int(match.group(3))
                    new_count = int(match.group(4) or 1)
                    
                    current_block = {
                        'old_start': old_start,
                        'old_count': old_count,
                        'new_start': new_start,
                        'new_count': new_count,
                        'lines': []
                    }
            # Handle content lines
            elif current_block:
                line_type = 'context'
                if line.startswith('+'):
                    line_type = 'addition'
                elif line.startswith('-'):
                    line_type = 'deletion'
                
                content = line[1:] if line.startswith(('+', '-', ' ')) else line
                
                current_block['lines'].append({
                    'type': line_type,
                    'content': content
                })
        
        # Add the last block
        if current_block:
            blocks.append(current_block)
        
        # If word diff is enabled, enhance the diff with word-level changes
        if word_diff:
            blocks = self._enhance_with_word_diff(blocks)
        
        return blocks
    
    def _enhance_with_word_diff(self, blocks):
        """Enhance diff blocks with word-level changes
        
        Args:
            blocks (list): List of diff blocks
            
        Returns:
            list: Enhanced diff blocks
        """
        for block in blocks:
            # Group lines by type
            deletions = []
            additions = []
            
            for i, line in enumerate(block['lines']):
                if line['type'] == 'deletion':
                    deletions.append((i, line['content']))
                elif line['type'] == 'addition':
                    additions.append((i, line['content']))
            
            # Process pairs of deletions and additions
            processed_indices = set()
            
            for d_idx, d_content in deletions:
                for a_idx, a_content in additions:
                    if a_idx in processed_indices:
                        continue
                    
                    # If the lines are similar, perform word diff
                    similarity = difflib.SequenceMatcher(None, d_content, a_content).ratio()
                    if similarity > 0.5:  # Threshold for considering lines similar
                        # Perform word diff
                        d_words = self._split_into_words(d_content)
                        a_words = self._split_into_words(a_content)
                        
                        matcher = difflib.SequenceMatcher(None, d_words, a_words)
                        opcodes = matcher.get_opcodes()
                        
                        # Create marked-up versions of the lines
                        d_marked = []
                        a_marked = []
                        
                        for tag, i1, i2, j1, j2 in opcodes:
                            if tag == 'equal':
                                d_marked.extend(d_words[i1:i2])
                                a_marked.extend(a_words[j1:j2])
                            elif tag == 'replace':
                                d_marked.append('<del>' + ' '.join(d_words[i1:i2]) + '</del>')
                                a_marked.append('<ins>' + ' '.join(a_words[j1:j2]) + '</ins>')
                            elif tag == 'delete':
                                d_marked.append('<del>' + ' '.join(d_words[i1:i2]) + '</del>')
                            elif tag == 'insert':
                                a_marked.append('<ins>' + ' '.join(a_words[j1:j2]) + '</ins>')
                        
                        # Update the block lines
                        block['lines'][d_idx]['word_diff'] = ' '.join(d_marked)
                        block['lines'][a_idx]['word_diff'] = ' '.join(a_marked)
                        
                        processed_indices.add(a_idx)
                        break
        
        return blocks
    
    def _split_into_words(self, text):
        """Split text into words for word-level diffing
        
        Args:
            text (str): Text to split
            
        Returns:
            list: List of words
        """
        # Split by whitespace but preserve punctuation
        return re.findall(r'\S+|\s+', text)
    
    def compare_sections(self, old_section, new_section):
        """Compare two sections and return a diff
        
        Args:
            old_section (dict): The old section data
            new_section (dict): The new section data
            
        Returns:
            dict: Diff information
        """
        # Extract content from sections
        old_content = old_section.get('content', '')
        new_content = new_section.get('content', '')
        
        # Compare the content
        content_diff = self.compare_text(old_content, new_content)
        
        # Compare subsections if present
        subsection_diffs = []
        
        old_subsections = old_section.get('subsections', [])
        new_subsections = new_section.get('subsections', [])
        
        # Map subsections by number for easier comparison
        old_subsection_map = {s.get('num'): s for s in old_subsections}
        new_subsection_map = {s.get('num'): s for s in new_subsections}
        
        # Find all subsection numbers
        all_subsection_nums = sorted(set(list(old_subsection_map.keys()) + list(new_subsection_map.keys())))
        
        for num in all_subsection_nums:
            old_subsection = old_subsection_map.get(num, {'content': ''})
            new_subsection = new_subsection_map.get(num, {'content': ''})
            
            # Compare subsection content
            old_content = old_subsection.get('content', '')
            new_content = new_subsection.get('content', '')
            
            subsection_diff = self.compare_text(old_content, new_content)
            
            # Only add if there are actual differences
            if subsection_diff:
                subsection_diffs.append({
                    'num': num,
                    'diff': subsection_diff,
                    'status': 'modified' if num in old_subsection_map and num in new_subsection_map else
                              'added' if num in new_subsection_map else 'deleted'
                })
        
        # Create the complete diff
        return {
            'section_num': new_section.get('num'),
            'heading': new_section.get('heading'),
            'content_diff': content_diff,
            'subsection_diffs': subsection_diffs,
            'status': 'modified' if old_section and new_section else
                      'added' if new_section else 'deleted'
        }
    
    def compare_chapters(self, old_chapter, new_chapter):
        """Compare two chapters and return a diff
        
        Args:
            old_chapter (dict): The old chapter data
            new_chapter (dict): The new chapter data
            
        Returns:
            dict: Diff information
        """
        # Extract sections from chapters
        old_sections = old_chapter.get('sections', [])
        new_sections = new_chapter.get('sections', [])
        
        # Map sections by number for easier comparison
        old_section_map = {s.get('num'): s for s in old_sections}
        new_section_map = {s.get('num'): s for s in new_sections}
        
        # Find all section numbers
        all_section_nums = sorted(set(list(old_section_map.keys()) + list(new_section_map.keys())))
        
        # Compare each section
        section_diffs = []
        
        for num in all_section_nums:
            old_section = old_section_map.get(num, {})
            new_section = new_section_map.get(num, {})
            
            # Skip if both are empty
            if not old_section and not new_section:
                continue
            
            # Compare the sections
            section_diff = self.compare_sections(old_section, new_section)
            
            # Only add if there are actual differences
            if section_diff:
                section_diffs.append(section_diff)
        
        # Create the complete diff
        return {
            'chapter_num': new_chapter.get('num'),
            'heading': new_chapter.get('heading'),
            'section_diffs': section_diffs,
            'status': 'modified' if old_chapter and new_chapter else
                      'added' if new_chapter else 'deleted'
        }
    
    def compare_titles(self, old_title, new_title):
        """Compare two titles and return a diff
        
        Args:
            old_title (dict): The old title data
            new_title (dict): The new title data
            
        Returns:
            dict: Diff information
        """
        # Extract chapters from titles
        old_chapters = old_title.get('content', {}).get('chapters', [])
        new_chapters = new_title.get('content', {}).get('chapters', [])
        
        # Map chapters by number for easier comparison
        old_chapter_map = {c.get('num'): c for c in old_chapters}
        new_chapter_map = {c.get('num'): c for c in new_chapters}
        
        # Find all chapter numbers
        all_chapter_nums = sorted(set(list(old_chapter_map.keys()) + list(new_chapter_map.keys())))
        
        # Compare each chapter
        chapter_diffs = []
        
        for num in all_chapter_nums:
            old_chapter = old_chapter_map.get(num, {})
            new_chapter = new_chapter_map.get(num, {})
            
            # Skip if both are empty
            if not old_chapter and not new_chapter:
                continue
            
            # Compare the chapters
            chapter_diff = self.compare_chapters(old_chapter, new_chapter)
            
            # Only add if there are actual differences
            if chapter_diff:
                chapter_diffs.append(chapter_diff)
        
        # Create the complete diff
        return {
            'title_num': new_title.get('title_num'),
            'name': new_title.get('name'),
            'chapter_diffs': chapter_diffs,
            'status': 'modified' if old_title and new_title else
                      'added' if new_title else 'deleted'
        }
    
    def generate_html_diff(self, diff_data, inline=True):
        """Generate HTML representation of a diff
        
        Args:
            diff_data (dict): Diff data from compare_text
            inline (bool): Whether to use inline or side-by-side view
            
        Returns:
            str: HTML representation of the diff
        """
        html_output = []
        
        # Add CSS styles
        html_output.append('''
        <style>
            .diff-container {
                font-family: monospace;
                white-space: pre-wrap;
                margin-bottom: 20px;
            }
            .diff-header {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #ccc;
                border-bottom: none;
                font-weight: bold;
            }
            .diff-content {
                border: 1px solid #ccc;
                overflow: auto;
            }
            .diff-line {
                padding: 0 5px;
                line-height: 1.5;
            }
            .diff-line-num {
                color: #999;
                padding-right: 10px;
                text-align: right;
                width: 40px;
                display: inline-block;
                user-select: none;
            }
            .diff-add {
                background-color: #e6ffed;
            }
            .diff-del {
                background-color: #ffeef0;
            }
            .diff-ctx {
                background-color: #f8f8f8;
            }
            ins {
                background-color: #acf2bd;
                text-decoration: none;
            }
            del {
                background-color: #fdb8c0;
                text-decoration: none;
            }
            
            /* Side-by-side specific styles */
            .diff-table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }
            .diff-table td {
                vertical-align: top;
                padding: 0;
            }
            .diff-old, .diff-new {
                width: 50%;
            }
        </style>
        ''')
        
        if isinstance(diff_data, list):
            # This is a text diff
            if inline:
                html_output.append(self._generate_inline_diff(diff_data))
            else:
                html_output.append(self._generate_side_by_side_diff(diff_data))
        elif isinstance(diff_data, dict):
            # This is a section/chapter/title diff
            if 'section_num' in diff_data:
                # Section diff
                html_output.append(f'<h2>Section {diff_data["section_num"]}: {diff_data["heading"]}</h2>')
                html_output.append(f'<p>Status: {diff_data["status"]}</p>')
                
                if diff_data['content_diff']:
                    html_output.append('<h3>Content Changes</h3>')
                    if inline:
                        html_output.append(self._generate_inline_diff(diff_data['content_diff']))
                    else:
                        html_output.append(self._generate_side_by_side_diff(diff_data['content_diff']))
                
                if diff_data['subsection_diffs']:
                    html_output.append('<h3>Subsection Changes</h3>')
                    for subsection_diff in diff_data['subsection_diffs']:
                        html_output.append(f'<h4>Subsection {subsection_diff["num"]} ({subsection_diff["status"]})</h4>')
                        if inline:
                            html_output.append(self._generate_inline_diff(subsection_diff['diff']))
                        else:
                            html_output.append(self._generate_side_by_side_diff(subsection_diff['diff']))
            
            elif 'chapter_num' in diff_data:
                # Chapter diff
                html_output.append(f'<h2>Chapter {diff_data["chapter_num"]}: {diff_data["heading"]}</h2>')
                html_output.append(f'<p>Status: {diff_data["status"]}</p>')
                
                if diff_data['section_diffs']:
                    for section_diff in diff_data['section_diffs']:
                        html_output.append(self.generate_html_diff(section_diff, inline))
            
            elif 'title_num' in diff_data:
                # Title diff
                html_output.append(f'<h1>Title {diff_data["title_num"]}: {diff_data["name"]}</h1>')
                html_output.append(f'<p>Status: {diff_data["status"]}</p>')
                
                if diff_data['chapter_diffs']:
                    for chapter_diff in diff_data['chapter_diffs']:
                        html_output.append(self.generate_html_diff(chapter_diff, inline))
        
        return '\n'.join(html_output)
    
    def _generate_inline_diff(self, diff_blocks):
        """Generate inline HTML diff
        
        Args:
            diff_blocks (list): List of diff blocks
            
        Returns:
            str: HTML representation
        """
        html_output = []
        
        for block in diff_blocks:
            # Add block header
            html_output.append(f'<div class="diff-container">')
            html_output.append(f'<div class="diff-header">@@ -{block["old_start"]},{block["old_count"]} +{block["new_start"]},{block["new_count"]} @@</div>')
            html_output.append(f'<div class="diff-content">')
            
            # Add lines
            old_line = block['old_start']
            new_line = block['new_start']
            
            for line in block['lines']:
                line_type = line['type']
                content = html.escape(line['content'])
                
                # Use word diff if available
                if 'word_diff' in line:
                    content = line['word_diff']
                
                css_class = ''
                prefix = ' '
                line_num = ''
                
                if line_type == 'context':
                    css_class = 'diff-ctx'
                    line_num = f'<span class="diff-line-num">{old_line}</span><span class="diff-line-num">{new_line}</span>'
                    old_line += 1
                    new_line += 1
                elif line_type == 'addition':
                    css_class = 'diff-add'
                    prefix = '+'
                    line_num = f'<span class="diff-line-num"></span><span class="diff-line-num">{new_line}</span>'
                    new_line += 1
                elif line_type == 'deletion':
                    css_class = 'diff-del'
                    prefix = '-'
                    line_num = f'<span class="diff-line-num">{old_line}</span><span class="diff-line-num"></span>'
                    old_line += 1
                
                html_output.append(f'<div class="diff-line {css_class}">{line_num}{prefix}{content}</div>')
            
            html_output.append('</div></div>')
        
        return '\n'.join(html_output)
    
    def _generate_side_by_side_diff(self, diff_blocks):
        """Generate side-by-side HTML diff
        
        Args:
            diff_blocks (list): List of diff blocks
            
        Returns:
            str: HTML representation
        """
        html_output = []
        
        for block in diff_blocks:
            # Add block header
            html_output.append(f'<div class="diff-container">')
            html_output.append(f'<div class="diff-header">@@ -{block["old_start"]},{block["old_count"]} +{block["new_start"]},{block["new_count"]} @@</div>')
            html_output.append(f'<div class="diff-content">')
            html_output.append(f'<table class="diff-table">')
            
            # Add table header
            html_output.append('<tr><td class="diff-old"><div class="diff-line diff-ctx">')
            html_output.append(f'<span class="diff-line-num">Line</span> Old')
            html_output.append('</div></td><td class="diff-new"><div class="diff-line diff-ctx">')
            html_output.append(f'<span class="diff-line-num">Line</span> New')
            html_output.append('</div></td></tr>')
            
            # Process lines
            old_line = block['old_start']
            new_line = block['new_start']
            
            for line in block['lines']:
                line_type = line['type']
                content = html.escape(line['content'])
                
                # Use word diff if available
                if 'word_diff' in line:
                    content = line['word_diff']
                
                if line_type == 'context':
                    html_output.append('<tr>')
                    html_output.append(f'<td class="diff-old"><div class="diff-line diff-ctx">')
                    html_output.append(f'<span class="diff-line-num">{old_line}</span> {content}')
                    html_output.append('</div></td>')
                    html_output.append(f'<td class="diff-new"><div class="diff-line diff-ctx">')
                    html_output.append(f'<span class="diff-line-num">{new_line}</span> {content}')
                    html_output.append('</div></td>')
                    html_output.append('</tr>')
                    old_line += 1
                    new_line += 1
                elif line_type == 'addition':
                    html_output.append('<tr>')
                    html_output.append(f'<td class="diff-old"><div class="diff-line"></div></td>')
                    html_output.append(f'<td class="diff-new"><div class="diff-line diff-add">')
                    html_output.append(f'<span class="diff-line-num">{new_line}</span> {content}')
                    html_output.append('</div></td>')
                    html_output.append('</tr>')
                    new_line += 1
                elif line_type == 'deletion':
                    html_output.append('<tr>')
                    html_output.append(f'<td class="diff-old"><div class="diff-line diff-del">')
                    html_output.append(f'<span class="diff-line-num">{old_line}</span> {content}')
                    html_output.append('</div></td>')
                    html_output.append(f'<td class="diff-new"><div class="diff-line"></div></td>')
                    html_output.append('</tr>')
                    old_line += 1
            
            html_output.append('</table>')
            html_output.append('</div></div>')
        
        return '\n'.join(html_output)
    
    def load_title_version(self, title_num, version):
        """Load a specific version of a title
        
        Args:
            title_num (int): Title number
            version (str): Version identifier (e.g., "119-4")
            
        Returns:
            dict: Title data or None if not found
        """
        # Format title number with leading zeros
        title_str = str(title_num).zfill(2)
        
        # Try to find the title file
        processed_dir = Path("processed")
        if not processed_dir.exists():
            logger.error("Processed directory not found")
            return None
        
        # Look for the specific version
        title_file = processed_dir / f"usc{title_str}_{version}.json"
        
        # If not found, try the regular file (current version)
        if not title_file.exists():
            title_file = processed_dir / f"usc{title_str}.json"
            
            if not title_file.exists():
                logger.error(f"Title {title_num} not found")
                return None
        
        # Load the title data
        try:
            with open(title_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading title {title_num}: {e}")
            return None
    
    def compare_title_versions(self, title_num, old_version, new_version):
        """Compare two versions of a title
        
        Args:
            title_num (int): Title number
            old_version (str): Old version identifier
            new_version (str): New version identifier
            
        Returns:
            dict: Diff information
        """
        # Load the title versions
        old_title = self.load_title_version(title_num, old_version)
        new_title = self.load_title_version(title_num, new_version)
        
        if not old_title or not new_title:
            logger.error(f"Could not load title {title_num} versions for comparison")
            return None
        
        # Compare the titles
        return self.compare_titles(old_title, new_title)
    
    def get_available_versions(self, title_num):
        """Get available versions for a title
        
        Args:
            title_num (int): Title number
            
        Returns:
            list: List of available versions
        """
        # Format title number with leading zeros
        title_str = str(title_num).zfill(2)
        
        # Try to find the title files
        processed_dir = Path("processed")
        if not processed_dir.exists():
            logger.error("Processed directory not found")
            return []
        
        # Look for all versions of this title
        title_files = list(processed_dir.glob(f"usc{title_str}_*.json"))
        
        # Extract version information
        versions = []
        for file in title_files:
            match = re.search(r'usc\d+_(.+)\.json', file.name)
            if match:
                version = match.group(1)
                versions.append(version)
        
        # Add the current version if it exists
        current_file = processed_dir / f"usc{title_str}.json"
        if current_file.exists():
            versions.append("current")
        
        return sorted(versions)

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='US Code Diff Visualizer')
    parser.add_argument('--title', type=int, help='Title number to compare')
    parser.add_argument('--old', help='Old version')
    parser.add_argument('--new', help='New version')
    parser.add_argument('--output', help='Output file for HTML diff')
    parser.add_argument('--side-by-side', action='store_true', help='Use side-by-side view instead of inline')
    parser.add_argument('--list-versions', type=int, help='List available versions for a title')
    
    args = parser.parse_args()
    
    visualizer = DiffVisualizer()
    
    if args.list_versions:
        versions = visualizer.get_available_versions(args.list_versions)
        if versions:
            print(f"Available versions for Title {args.list_versions}:")
            for version in versions:
                print(f"  {version}")
        else:
            print(f"No versions found for Title {args.list_versions}")
    
    elif args.title and args.old and args.new:
        diff = visualizer.compare_title_versions(args.title, args.old, args.new)
        
        if diff:
            html_diff = visualizer.generate_html_diff(diff, not args.side_by_side)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(html_diff)
                print(f"Diff saved to {args.output}")
            else:
                print(html_diff)
        else:
            print(f"Failed to generate diff for Title {args.title}")
    
    else:
        parser.print_help()
