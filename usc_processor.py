import xml.etree.ElementTree as ET
import json
import zipfile
import re
from pathlib import Path
import shutil
import logging
import traceback
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('usc_processor.log')
    ]
)

# Create a logger for this module
logger = logging.getLogger('usc_processor')

# Custom exception classes
class USCProcessorError(Exception):
    """Base exception for USC Processor errors"""
    pass

class XMLParsingError(USCProcessorError):
    """Exception raised for XML parsing errors"""
    pass

class EncodingError(USCProcessorError):
    """Exception raised for encoding errors"""
    pass

class ZipExtractionError(USCProcessorError):
    """Exception raised for ZIP extraction errors"""
    pass

class USCProcessor:
    def __init__(self, download_dir="downloads", output_dir="processed"):
        self.download_dir = Path(download_dir)
        self.output_dir = Path(output_dir)
        self.ns = {
            'uslm': 'http://xml.house.gov/schemas/uslm/1.0',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        # Use the module logger
        self.logger = logger

    def process_downloads(self):
        """Process all USC zip files in download directory"""
        self.download_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self.logger.info(f"Processing all zip files in {self.download_dir}")
        zip_files = list(self.download_dir.glob('*.zip'))
        self.logger.info(f"Found {len(zip_files)} zip files")

        for zip_file in zip_files:
            self.logger.info(f"Processing {zip_file}")
            self.process_zip_file(zip_file)

    def process_zip_file(self, zip_path):
        """Extract and process a single USC zip file

        Args:
            zip_path (Path): Path to the zip file to process

        Raises:
            ZipExtractionError: If there's an error extracting the zip file
            XMLParsingError: If there's an error parsing the XML files
        """
        # Make sure output directory exists
        self.output_dir.mkdir(exist_ok=True)

        # Create temp directory for extraction
        temp_dir = self.output_dir / 'temp'
        temp_dir.mkdir(exist_ok=True)

        try:
            # Extract zip file
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # List all files in the zip
                    file_list = zip_ref.namelist()
                    self.logger.info(f"Zip contains {len(file_list)} files")

                    # Extract all files
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile as e:
                raise ZipExtractionError(f"Invalid zip file {zip_path}: {e}") from e
            except PermissionError as e:
                raise ZipExtractionError(f"Permission denied when extracting {zip_path}: {e}") from e
            except Exception as e:
                raise ZipExtractionError(f"Error extracting {zip_path}: {e}") from e

            # Process all XML files (including those in subdirectories)
            xml_files = list(temp_dir.glob('**/*.xml'))
            self.logger.info(f"Found {len(xml_files)} XML files")

            if not xml_files:
                self.logger.warning(f"No XML files found in {zip_path}")

            successful_files = 0
            for xml_file in xml_files:
                try:
                    self.logger.info(f"Processing XML file: {xml_file.name}")
                    self.process_xml_file(xml_file)
                    successful_files += 1
                except XMLParsingError as e:
                    self.logger.error(f"XML parsing error in {xml_file}: {e}")
                except EncodingError as e:
                    self.logger.error(f"Encoding error in {xml_file}: {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error processing {xml_file}: {e}")
                    self.logger.debug(f"Traceback: {traceback.format_exc()}")

            # Extract title and release information from zip filename
            title_info = self.extract_title_info(zip_path.name)
            if title_info:
                self.logger.info(f"Processed Title {title_info['title']} (Release {title_info['release']})")
                self.logger.info(f"Successfully processed {successful_files} out of {len(xml_files)} XML files")

            # Keep the zip file for reference
            # zip_path.unlink()
            self.logger.info(f"Finished processing {zip_path}")

        except ZipExtractionError as e:
            self.logger.error(f"{e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error processing zip file {zip_path}: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                self.logger.warning(f"Error cleaning up temp directory {temp_dir}: {e}")

        return True

    def extract_title_info(self, filename):
        """Extract title number and release information from filename"""
        # Pattern for standard title zip: title01.zip or title01_119-4.zip
        title_pattern = re.compile(r'title(\d+)(?:_(\d+-\d+))?\.zip')
        # Pattern for release point zip: xml_usc01@119-4.zip
        release_pattern = re.compile(r'xml_usc(\d+)@(\d+-\d+)\.zip')

        title_match = title_pattern.match(filename)
        release_match = release_pattern.match(filename)

        if title_match:
            title_num = title_match.group(1)
            release = title_match.group(2) if title_match.group(2) else 'unknown'
            return {'title': title_num, 'release': release}
        elif release_match:
            title_num = release_match.group(1)
            release = release_match.group(2)
            return {'title': title_num, 'release': release}

        return None

    def process_xml_file(self, xml_path):
        """Convert single XML file to JSON structure

        Args:
            xml_path (Path): Path to the XML file to process

        Raises:
            XMLParsingError: If there's an error parsing the XML file
            EncodingError: If there's an encoding error in the XML file
        """
        try:
            try:
                tree = ET.parse(xml_path)
                root = tree.getroot()
            except ET.ParseError as e:
                raise XMLParsingError(f"Error parsing XML file {xml_path}: {e}") from e
            except UnicodeDecodeError as e:
                raise EncodingError(f"Encoding error in XML file {xml_path}: {e}") from e
            except Exception as e:
                raise XMLParsingError(f"Unexpected error parsing XML file {xml_path}: {e}") from e

            # Extract metadata
            try:
                metadata = self.extract_metadata(root)
                # Log metadata for debugging
                self.logger.info(f"Metadata found: {metadata}")
            except Exception as e:
                self.logger.warning(f"Error extracting metadata from {xml_path}: {e}")
                metadata = {"identifier": xml_path.stem, "title": "Unknown Title"}

            # Extract main content
            try:
                content = self.extract_content(root)
            except Exception as e:
                self.logger.warning(f"Error extracting content from {xml_path}: {e}")
                content = {"title": {}, "chapters": [], "sections": []}

            # Combine into final structure
            usc_data = {
                "metadata": metadata,
                "content": content
            }

            # Create a more descriptive filename
            title_match = re.search(r'usc(\d+)', metadata.get('identifier', ''))
            if title_match:
                title_num = title_match.group(1)
                # Use a more descriptive filename including the title number
                json_filename = f"usc{title_num}.json"
            else:
                # Fallback to original filename
                json_filename = f"{xml_path.stem}.json"

            # Save as JSON
            json_path = self.output_dir / json_filename
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(usc_data, f, indent=2)
                self.logger.info(f"Saved JSON to {json_path}")
            except Exception as e:
                self.logger.error(f"Error saving JSON to {json_path}: {e}")
                raise
        except (XMLParsingError, EncodingError):
            # Re-raise these specific exceptions to be caught by the caller
            raise
        except Exception as e:
            # Catch any other exceptions and convert to XMLParsingError
            self.logger.error(f"Unexpected error processing {xml_path}: {e}")
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            raise XMLParsingError(f"Unexpected error processing {xml_path}: {e}") from e

    def extract_metadata(self, root):
        """Extract metadata from USC XML"""
        # Get the root identifier attribute if available
        root_identifier = root.get('identifier', '')

        meta = root.find('.//uslm:meta', self.ns)
        if meta is None:
            self.logger.warning("No metadata element found in XML")
            # Create basic metadata from root attributes
            return {
                "identifier": root_identifier,
                "title": root.get('title', 'Unknown Title')
            }

        # Extract standard metadata fields
        metadata = {
            "identifier": root_identifier or self.get_text(meta, './/dc:identifier'),
            "title": self.get_text(meta, './/dc:title'),
            "publisher": self.get_text(meta, './/dc:publisher'),
            "created": self.get_text(meta, './/dcterms:created'),
            "type": self.get_text(meta, './/dc:type')
        }

        # Add document number if available
        doc_number = self.get_text(meta, './/docNumber')
        if doc_number:
            metadata["docNumber"] = doc_number

        # Add publication name if available
        pub_name = self.get_text(meta, './/docPublicationName')
        if pub_name:
            metadata["publicationName"] = pub_name

        # Extract release information from publication name
        if pub_name and '@' in pub_name:
            release_match = re.search(r'@(\d+-\d+)', pub_name)
            if release_match:
                metadata["release"] = release_match.group(1)

        # Add additional metadata if available
        if self.get_text(meta, './/dc:description'):
            metadata["description"] = self.get_text(meta, './/dc:description')

        if self.get_text(meta, './/dc:date'):
            metadata["date"] = self.get_text(meta, './/dc:date')

        return metadata

    def extract_content(self, root):
        """Extract main content structure from USC XML"""
        main = root.find('.//uslm:main', self.ns)
        if main is None:
            self.logger.warning("No main element found in XML")
            return {}

        # Extract title information
        title_element = main.find('.//uslm:title', self.ns)
        if title_element is not None:
            title_info = {
                "num": self.get_text(title_element, './/uslm:num'),
                "heading": self.get_text(title_element, './/uslm:heading'),
                "identifier": title_element.get('identifier', '')
            }
            self.logger.info(f"Found title: {title_info['num']} - {title_info['heading']}")
        else:
            title_info = {}
            self.logger.warning("No title element found in XML")

        # Extract chapters
        chapters = []
        chapter_elements = main.findall('.//uslm:chapter', self.ns)
        self.logger.info(f"Found {len(chapter_elements)} chapters")

        for chapter in chapter_elements:
            try:
                chapter_data = {
                    "num": self.get_text(chapter, './/uslm:num'),
                    "heading": self.get_text(chapter, './/uslm:heading'),
                    "identifier": chapter.get('identifier', ''),
                    "sections": []
                }

                # Extract sections within this chapter
                section_elements = chapter.findall('.//uslm:section', self.ns)
                for section in section_elements:
                    try:
                        section_data = {
                            "num": self.get_text(section, './/uslm:num'),
                            "heading": self.get_text(section, './/uslm:heading'),
                            "content": self.get_text(section, './/uslm:content'),
                            "identifier": section.get('identifier', ''),
                            "subsections": self.extract_subsections(section)
                        }
                        chapter_data["sections"].append(section_data)
                    except Exception as e:
                        self.logger.error(f"Error extracting section data: {e}")

                chapters.append(chapter_data)
            except Exception as e:
                self.logger.error(f"Error extracting chapter data: {e}")

        # Also extract any sections directly under main (not in chapters)
        sections = []
        direct_sections = main.findall('./uslm:section', self.ns)
        self.logger.info(f"Found {len(direct_sections)} direct sections")

        for section in direct_sections:
            try:
                section_data = {
                    "num": self.get_text(section, './/uslm:num'),
                    "heading": self.get_text(section, './/uslm:heading'),
                    "content": self.get_text(section, './/uslm:content'),
                    "identifier": section.get('identifier', ''),
                    "subsections": self.extract_subsections(section)
                }
                sections.append(section_data)
            except Exception as e:
                self.logger.error(f"Error extracting section data: {e}")

        # Combine all content
        content = {
            "title": title_info,
            "chapters": chapters,
            "sections": sections
        }

        return content

    def extract_subsections(self, section):
        """Extract subsection hierarchy"""
        subsections = []
        for subsec in section.findall('.//uslm:subsection', self.ns):
            try:
                subsection_data = {
                    "num": self.get_text(subsec, './/uslm:num'),
                    "content": self.get_text(subsec, './/uslm:content')
                }

                # Add subsection identifier if available
                if subsec.get('identifier'):
                    subsection_data["identifier"] = subsec.get('identifier')

                # Extract paragraphs within subsections if they exist
                paragraphs = self.extract_paragraphs(subsec)
                if paragraphs:
                    subsection_data["paragraphs"] = paragraphs

                subsections.append(subsection_data)
            except Exception as e:
                self.logger.error(f"Error extracting subsection data: {e}")

        return subsections

    def extract_paragraphs(self, parent):
        """Extract paragraph hierarchy"""
        paragraphs = []
        for para in parent.findall('.//uslm:paragraph', self.ns):
            try:
                paragraph_data = {
                    "num": self.get_text(para, './/uslm:num'),
                    "content": self.get_text(para, './/uslm:content')
                }

                # Add paragraph identifier if available
                if para.get('identifier'):
                    paragraph_data["identifier"] = para.get('identifier')

                # Extract subparagraphs if they exist
                subparagraphs = self.extract_subparagraphs(para)
                if subparagraphs:
                    paragraph_data["subparagraphs"] = subparagraphs

                paragraphs.append(paragraph_data)
            except Exception as e:
                self.logger.error(f"Error extracting paragraph data: {e}")

        return paragraphs

    def extract_subparagraphs(self, parent):
        """Extract subparagraph hierarchy"""
        subparagraphs = []
        for subpara in parent.findall('.//uslm:subparagraph', self.ns):
            try:
                subparagraph_data = {
                    "num": self.get_text(subpara, './/uslm:num'),
                    "content": self.get_text(subpara, './/uslm:content')
                }

                # Add subparagraph identifier if available
                if subpara.get('identifier'):
                    subparagraph_data["identifier"] = subpara.get('identifier')

                subparagraphs.append(subparagraph_data)
            except Exception as e:
                self.logger.error(f"Error extracting subparagraph data: {e}")

        return subparagraphs

    def get_text(self, element, xpath):
        """Helper to safely extract text from XML elements

        Args:
            element (Element): The XML element to search within
            xpath (str): The XPath expression to find the target element

        Returns:
            str: The extracted text, or an empty string if not found or on error

        Raises:
            EncodingError: If there's an encoding error that can't be handled
        """
        found = element.find(xpath, self.ns)
        if found is not None:
            try:
                # If the element has children, get all text including from child elements
                if len(found) > 0:
                    # Join all text and handle potential encoding issues
                    text = ''.join(found.itertext())
                    return text.strip() if text else ""
                # Otherwise just get the text
                elif found.text:
                    return found.text.strip()
                return ""
            except UnicodeDecodeError as e:
                self.logger.warning(f"Unicode decode error extracting text: {e}")
                # Try to sanitize the text if there's an encoding issue
                try:
                    if len(found) > 0:
                        # Get all text and encode/decode to handle problematic characters
                        text_parts = []
                        for part in found.itertext():
                            try:
                                # Handle potential encoding issues by re-encoding with error handling
                                if isinstance(part, str):
                                    sanitized = part.encode('utf-8', 'ignore').decode('utf-8')
                                    text_parts.append(sanitized)
                            except Exception as part_error:
                                self.logger.debug(f"Skipping problematic text part: {part_error}")
                        return ''.join(text_parts).strip()
                    elif found.text:
                        # Encode and decode to handle problematic characters
                        if isinstance(found.text, str):
                            return found.text.encode('utf-8', 'ignore').decode('utf-8').strip()
                        return ""
                except Exception as e2:
                    self.logger.error(f"Failed to sanitize text: {e2}")
                    # If we can't handle the encoding issue, raise an EncodingError
                    # but with a fallback empty string for non-critical text
                    if xpath.endswith('content'):
                        raise EncodingError(f"Critical encoding error in content: {e2}") from e2
                    return ""
            except Exception as e:
                self.logger.warning(f"Error extracting text: {e}")
                # For non-encoding errors, just return empty string
                return ""
        return ""

if __name__ == "__main__":
    import argparse

    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Process USC XML files')
    parser.add_argument('--download-dir', default='downloads', help='Directory containing zip files')
    parser.add_argument('--output-dir', default='processed', help='Directory for output JSON files')
    parser.add_argument('--file', help='Process a specific zip file')

    args = parser.parse_args()

    # Initialize processor
    processor = USCProcessor(download_dir=args.download_dir, output_dir=args.output_dir)

    # Process specific file or all files
    if args.file:
        file_path = Path(args.file)
        if file_path.exists() and file_path.is_file() and file_path.suffix.lower() == '.zip':
            processor.process_zip_file(file_path)
        else:
            processor.logger.error(f"Invalid file: {args.file}")
    else:
        processor.process_downloads()