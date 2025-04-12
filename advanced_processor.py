import json
import re
import logging
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import os
# Try to import optional dependencies
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
    # Download NLTK data
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except ImportError:
    NLTK_AVAILABLE = False
    print("NLTK not available. Some features will be disabled.")

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    print("NetworkX or Matplotlib not available. Graph generation will be disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('advanced_processor.log')
    ]
)

logger = logging.getLogger('advanced_processor')

class AdvancedProcessor:
    def __init__(self, processed_dir="processed", download_dir="downloads", output_dir="advanced_processed"):
        self.processed_dir = Path(processed_dir)
        self.download_dir = Path(download_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Create directories for advanced processing outputs
        self.cross_refs_dir = self.output_dir / "cross_references"
        self.cross_refs_dir.mkdir(exist_ok=True)

        self.amendments_dir = self.output_dir / "amendments"
        self.amendments_dir.mkdir(exist_ok=True)

        self.notes_dir = self.output_dir / "notes"
        self.notes_dir.mkdir(exist_ok=True)

        self.graphs_dir = self.output_dir / "graphs"
        self.graphs_dir.mkdir(exist_ok=True)

        self.ns = {
            'uslm': 'http://xml.house.gov/schemas/uslm/1.0',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/'
        }

    def process_all_titles(self):
        """Process all titles with advanced features"""
        # Get all JSON files in the processed directory
        json_files = list(self.processed_dir.glob("*.json"))

        logger.info(f"Found {len(json_files)} processed titles")

        # Process each title
        for json_file in json_files:
            try:
                title_match = re.search(r'usc(\d+)\.json', json_file.name)
                if title_match:
                    title_num = int(title_match.group(1))
                    logger.info(f"Processing Title {title_num} with advanced features...")

                    # Load the JSON data
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Extract cross-references
                    cross_refs = self.extract_cross_references(data, title_num)

                    # Extract amendments
                    amendments = self.extract_amendments(data, title_num)

                    # Extract notes
                    notes = self.extract_notes(data, title_num)

                    # Generate cross-reference graph
                    self.generate_cross_reference_graph(cross_refs, title_num)

                    logger.info(f"Completed advanced processing for Title {title_num}")
            except Exception as e:
                logger.error(f"Error processing {json_file.name}: {e}")

    def extract_cross_references(self, data, title_num):
        """Extract cross-references from a title"""
        logger.info(f"Extracting cross-references for Title {title_num}...")

        cross_refs = []

        # Regular expressions for common cross-reference patterns
        patterns = [
            r'section (\d+) of title (\d+)',
            r'(\d+) U\.S\.C\. (\d+)',
            r'title (\d+), section (\d+)',
            r'see (\d+) U\.S\.C\. (\d+)',
            r'under section (\d+) of title (\d+)'
        ]

        # Function to extract cross-references from text
        def extract_from_text(text, source):
            if not text:
                return

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        if len(match.groups()) >= 2:
                            ref_section = match.group(1)
                            ref_title = match.group(2)

                            cross_refs.append({
                                'source_title': title_num,
                                'source_location': source,
                                'referenced_title': int(ref_title),
                                'referenced_section': int(ref_section),
                                'context': text[max(0, match.start() - 50):min(len(text), match.end() + 50)]
                            })
                    except:
                        pass

        # Extract from content
        if 'content' in data:
            # Extract from chapters
            for chapter_idx, chapter in enumerate(data['content'].get('chapters', [])):
                chapter_num = chapter_idx + 1

                # Extract from chapter content
                if 'content' in chapter:
                    extract_from_text(chapter['content'], f"Chapter {chapter_num}")

                # Extract from sections
                for section_idx, section in enumerate(chapter.get('sections', [])):
                    section_num = section_idx + 1

                    # Extract from section content
                    if 'content' in section:
                        extract_from_text(section['content'], f"Chapter {chapter_num}, Section {section_num}")

                    # Extract from subsections
                    for subsec_idx, subsection in enumerate(section.get('subsections', [])):
                        subsec_num = subsec_idx + 1

                        # Extract from subsection content
                        if 'content' in subsection:
                            extract_from_text(subsection['content'], f"Chapter {chapter_num}, Section {section_num}, Subsection {subsec_num}")

        # Save cross-references to file
        output_file = self.cross_refs_dir / f"title{title_num}_cross_refs.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cross_refs, f, indent=2)

        logger.info(f"Found {len(cross_refs)} cross-references in Title {title_num}")

        return cross_refs

    def extract_amendments(self, data, title_num):
        """Extract amendments from a title"""
        logger.info(f"Extracting amendments for Title {title_num}...")

        amendments = []

        # Regular expressions for common amendment patterns
        patterns = [
            r'amended by ([^\.]+)',
            r'as amended by ([^\.]+)',
            r'Public Law (\d+-\d+)',
            r'amended, effective ([^,\.]+), by ([^\.]+)'
        ]

        # Function to extract amendments from text
        def extract_from_text(text, source):
            if not text:
                return

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        amendments.append({
                            'title': title_num,
                            'location': source,
                            'amendment_text': match.group(0),
                            'context': text[max(0, match.start() - 50):min(len(text), match.end() + 50)]
                        })
                    except:
                        pass

        # Extract from content
        if 'content' in data:
            # Extract from chapters
            for chapter_idx, chapter in enumerate(data['content'].get('chapters', [])):
                chapter_num = chapter_idx + 1

                # Extract from chapter content
                if 'content' in chapter:
                    extract_from_text(chapter['content'], f"Chapter {chapter_num}")

                # Extract from sections
                for section_idx, section in enumerate(chapter.get('sections', [])):
                    section_num = section_idx + 1

                    # Extract from section content
                    if 'content' in section:
                        extract_from_text(section['content'], f"Chapter {chapter_num}, Section {section_num}")

                    # Extract from subsections
                    for subsec_idx, subsection in enumerate(section.get('subsections', [])):
                        subsec_num = subsec_idx + 1

                        # Extract from subsection content
                        if 'content' in subsection:
                            extract_from_text(subsection['content'], f"Chapter {chapter_num}, Section {section_num}, Subsection {subsec_num}")

        # Save amendments to file
        output_file = self.amendments_dir / f"title{title_num}_amendments.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(amendments, f, indent=2)

        logger.info(f"Found {len(amendments)} amendments in Title {title_num}")

        return amendments

    def extract_notes(self, data, title_num):
        """Extract notes from a title"""
        logger.info(f"Extracting notes for Title {title_num}...")

        notes = []

        # Function to extract notes from the original XML
        def extract_notes_from_xml():
            # Find the ZIP file for this title
            title_str = str(title_num).zfill(2)
            zip_files = list(self.download_dir.glob(f"title{title_str}_*.zip"))

            if not zip_files:
                logger.warning(f"No ZIP file found for Title {title_num}")
                return []

            # Extract the XML file
            with zipfile.ZipFile(zip_files[0], 'r') as zip_ref:
                xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]

                if not xml_files:
                    logger.warning(f"No XML file found in ZIP for Title {title_num}")
                    return []

                # Extract the first XML file
                xml_file = xml_files[0]
                zip_ref.extract(xml_file, self.output_dir)

                # Parse the XML file
                tree = ET.parse(self.output_dir / xml_file)
                root = tree.getroot()

                # Find all notes
                xml_notes = []
                for note_elem in root.findall('.//uslm:note', self.ns):
                    try:
                        note_type = note_elem.get('type', '')
                        note_topic = note_elem.get('topic', '')
                        note_text = ''.join(note_elem.itertext()).strip()

                        xml_notes.append({
                            'type': note_type,
                            'topic': note_topic,
                            'text': note_text
                        })
                    except Exception as e:
                        logger.error(f"Error extracting note: {e}")

                # Clean up
                os.remove(self.output_dir / xml_file)

                return xml_notes

        # Extract notes from XML
        xml_notes = extract_notes_from_xml()

        # Extract notes from JSON data
        json_notes = []

        # Regular expressions for common note patterns
        patterns = [
            r'NOTE: ([^\.]+)',
            r'NOTES: ([^\.]+)',
            r'HISTORICAL AND REVISION NOTES([^\.]+)'
        ]

        # Function to extract notes from text
        def extract_from_text(text, source):
            if not text:
                return

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        json_notes.append({
                            'title': title_num,
                            'location': source,
                            'note_text': match.group(0),
                            'context': text[max(0, match.start() - 50):min(len(text), match.end() + 50)]
                        })
                    except:
                        pass

        # Extract from content
        if 'content' in data:
            # Extract from chapters
            for chapter_idx, chapter in enumerate(data['content'].get('chapters', [])):
                chapter_num = chapter_idx + 1

                # Extract from chapter content
                if 'content' in chapter:
                    extract_from_text(chapter['content'], f"Chapter {chapter_num}")

                # Extract from sections
                for section_idx, section in enumerate(chapter.get('sections', [])):
                    section_num = section_idx + 1

                    # Extract from section content
                    if 'content' in section:
                        extract_from_text(section['content'], f"Chapter {chapter_num}, Section {section_num}")

        # Combine notes
        notes = {
            'xml_notes': xml_notes,
            'json_notes': json_notes
        }

        # Save notes to file
        output_file = self.notes_dir / f"title{title_num}_notes.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2)

        logger.info(f"Found {len(xml_notes)} XML notes and {len(json_notes)} JSON notes in Title {title_num}")

        return notes

    def generate_cross_reference_graph(self, cross_refs, title_num):
        """Generate a graph of cross-references"""
        logger.info(f"Generating cross-reference graph for Title {title_num}...")

        # Skip if NetworkX or Matplotlib is not available
        if not GRAPH_AVAILABLE:
            logger.warning("Graph generation disabled due to missing dependencies")
            return

        # Create a directed graph
        G = nx.DiGraph()

        # Add nodes and edges
        for ref in cross_refs:
            source = f"Title {ref['source_title']}"
            target = f"Title {ref['referenced_title']}"

            # Add nodes
            if source not in G:
                G.add_node(source)
            if target not in G:
                G.add_node(target)

            # Add edge
            if G.has_edge(source, target):
                # Increment weight if edge already exists
                G[source][target]['weight'] += 1
            else:
                # Create new edge with weight 1
                G.add_edge(source, target, weight=1)

        # Only generate graph if there are edges
        if G.number_of_edges() > 0:
            try:
                # Set up the plot
                plt.figure(figsize=(12, 8))

                # Calculate node positions
                pos = nx.spring_layout(G)

                # Get edge weights
                weights = [G[u][v]['weight'] for u, v in G.edges()]

                # Draw the graph
                nx.draw_networkx_nodes(G, pos, node_size=500, node_color='lightblue')
                nx.draw_networkx_labels(G, pos, font_size=10)
                nx.draw_networkx_edges(G, pos, width=weights, edge_color='gray', arrows=True)

                # Add edge labels (weights)
                edge_labels = {(u, v): G[u][v]['weight'] for u, v in G.edges()}
                nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

                # Set title and save
                plt.title(f"Cross-references from Title {title_num}")
                plt.axis('off')

                # Save the graph
                output_file = self.graphs_dir / f"title{title_num}_cross_refs_graph.png"
                plt.savefig(output_file, bbox_inches='tight')
                plt.close()

                logger.info(f"Saved cross-reference graph to {output_file}")
            except Exception as e:
                logger.error(f"Error generating graph: {e}")
        else:
            logger.info(f"No cross-references found for Title {title_num}, skipping graph generation")

if __name__ == "__main__":
    processor = AdvancedProcessor()
    processor.process_all_titles()
