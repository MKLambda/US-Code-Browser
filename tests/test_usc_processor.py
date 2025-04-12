import unittest
import os
import json
import shutil
from pathlib import Path
import zipfile
import tempfile
import xml.etree.ElementTree as ET

# Import the USCProcessor class
from usc_processor import USCProcessor

class TestUSCProcessor(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        # Create temporary directories for testing
        self.test_download_dir = Path("test_downloads")
        self.test_output_dir = Path("test_processed")
        
        # Create the directories
        self.test_download_dir.mkdir(exist_ok=True)
        self.test_output_dir.mkdir(exist_ok=True)
        
        # Initialize the processor with test directories
        self.processor = USCProcessor(
            download_dir=str(self.test_download_dir),
            output_dir=str(self.test_output_dir)
        )
        
        # Create a sample XML content for testing
        self.sample_xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" 
        xmlns:dc="http://purl.org/dc/elements/1.1/" 
        xmlns:dcterms="http://purl.org/dc/terms/">
    <meta>
        <dc:title>Sample Title</dc:title>
        <dc:identifier>usc/title1/sample</dc:identifier>
        <dc:publisher>U.S. Government Publishing Office</dc:publisher>
        <dcterms:created>2023-01-01</dcterms:created>
        <docReleasePoint>2023-01-01</docReleasePoint>
    </meta>
    <main>
        <section>
            <num>§ 1.</num>
            <heading>Sample Section Heading</heading>
            <content>This is sample section content.</content>
            <subsection>
                <num>(a)</num>
                <content>This is a sample subsection content.</content>
            </subsection>
            <subsection>
                <num>(b)</num>
                <content>This is another sample subsection content.</content>
            </subsection>
        </section>
        <section>
            <num>§ 2.</num>
            <heading>Another Sample Section</heading>
            <content>This is another sample section content.</content>
        </section>
    </main>
</uscDoc>
"""
    
    def tearDown(self):
        """Clean up after each test"""
        # Remove test directories and their contents
        if self.test_download_dir.exists():
            shutil.rmtree(self.test_download_dir)
        
        if self.test_output_dir.exists():
            shutil.rmtree(self.test_output_dir)
    
    def create_test_xml_file(self, filename="sample.xml"):
        """Helper method to create a test XML file"""
        xml_path = self.test_download_dir / filename
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(self.sample_xml_content)
        return xml_path
    
    def create_test_zip_file(self, zip_filename="sample.zip", xml_filename="sample.xml"):
        """Helper method to create a test ZIP file containing an XML file"""
        # Create the XML file first
        xml_path = self.create_test_xml_file(xml_filename)
        
        # Create a ZIP file containing the XML file
        zip_path = self.test_download_dir / zip_filename
        with zipfile.ZipFile(zip_path, 'w') as zip_file:
            zip_file.write(xml_path, arcname=xml_filename)
        
        return zip_path
    
    def test_init(self):
        """Test the initialization of USCProcessor"""
        self.assertEqual(self.processor.download_dir, Path(self.test_download_dir))
        self.assertEqual(self.processor.output_dir, Path(self.test_output_dir))
        self.assertIn('uslm', self.processor.ns)
        self.assertIn('dc', self.processor.ns)
        self.assertIn('dcterms', self.processor.ns)
    
    def test_get_text(self):
        """Test the get_text method"""
        # Parse the sample XML
        root = ET.fromstring(self.sample_xml_content)
        
        # Test with existing element
        title = self.processor.get_text(root.find('.//meta', self.processor.ns), './/dc:title')
        self.assertEqual(title, "Sample Title")
        
        # Test with non-existing element
        non_existing = self.processor.get_text(root, './/non-existing')
        self.assertEqual(non_existing, "")
    
    def test_extract_metadata(self):
        """Test the extract_metadata method"""
        # Parse the sample XML
        root = ET.fromstring(self.sample_xml_content)
        
        # Extract metadata
        metadata = self.processor.extract_metadata(root)
        
        # Verify the extracted metadata
        self.assertEqual(metadata['title'], "Sample Title")
        self.assertEqual(metadata['identifier'], "usc/title1/sample")
        self.assertEqual(metadata['publisher'], "U.S. Government Publishing Office")
        self.assertEqual(metadata['created'], "2023-01-01")
        self.assertEqual(metadata['docReleasePoint'], "2023-01-01")
    
    def test_extract_subsections(self):
        """Test the extract_subsections method"""
        # Parse the sample XML
        root = ET.fromstring(self.sample_xml_content)
        
        # Find a section element
        section = root.find('.//section', self.processor.ns)
        
        # Extract subsections
        subsections = self.processor.extract_subsections(section)
        
        # Verify the extracted subsections
        self.assertEqual(len(subsections), 2)
        self.assertEqual(subsections[0]['num'], "(a)")
        self.assertEqual(subsections[0]['content'], "This is a sample subsection content.")
        self.assertEqual(subsections[1]['num'], "(b)")
        self.assertEqual(subsections[1]['content'], "This is another sample subsection content.")
    
    def test_extract_content(self):
        """Test the extract_content method"""
        # Parse the sample XML
        root = ET.fromstring(self.sample_xml_content)
        
        # Extract content
        content = self.processor.extract_content(root)
        
        # Verify the extracted content
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]['num'], "§ 1.")
        self.assertEqual(content[0]['heading'], "Sample Section Heading")
        self.assertEqual(content[0]['content'], "This is sample section content.")
        self.assertEqual(len(content[0]['subsections']), 2)
        
        self.assertEqual(content[1]['num'], "§ 2.")
        self.assertEqual(content[1]['heading'], "Another Sample Section")
        self.assertEqual(content[1]['content'], "This is another sample section content.")
        self.assertEqual(len(content[1]['subsections']), 0)
    
    def test_process_xml_file(self):
        """Test the process_xml_file method"""
        # Create a test XML file
        xml_path = self.create_test_xml_file()
        
        # Process the XML file
        self.processor.process_xml_file(xml_path)
        
        # Check if the JSON file was created
        json_path = self.test_output_dir / f"{xml_path.stem}.json"
        self.assertTrue(json_path.exists())
        
        # Verify the content of the JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check metadata
        self.assertEqual(data['metadata']['title'], "Sample Title")
        
        # Check content
        self.assertEqual(len(data['content']), 2)
        self.assertEqual(data['content'][0]['num'], "§ 1.")
        self.assertEqual(data['content'][1]['num'], "§ 2.")
    
    def test_process_zip_file(self):
        """Test the process_zip_file method"""
        # Create a test ZIP file
        zip_path = self.create_test_zip_file()
        
        # Process the ZIP file
        self.processor.process_zip_file(zip_path)
        
        # Check if the JSON file was created
        json_path = self.test_output_dir / "sample.json"
        self.assertTrue(json_path.exists())
        
        # Verify the content of the JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check metadata
        self.assertEqual(data['metadata']['title'], "Sample Title")
        
        # Check content
        self.assertEqual(len(data['content']), 2)
        
        # Check if the ZIP file was removed
        self.assertFalse(zip_path.exists())
    
    def test_process_downloads(self):
        """Test the process_downloads method"""
        # Create multiple test ZIP files
        self.create_test_zip_file("sample1.zip", "sample1.xml")
        self.create_test_zip_file("sample2.zip", "sample2.xml")
        
        # Process all downloads
        self.processor.process_downloads()
        
        # Check if the JSON files were created
        json_path1 = self.test_output_dir / "sample1.json"
        json_path2 = self.test_output_dir / "sample2.json"
        
        self.assertTrue(json_path1.exists())
        self.assertTrue(json_path2.exists())
        
        # Check if the ZIP files were removed
        zip_path1 = self.test_download_dir / "sample1.zip"
        zip_path2 = self.test_download_dir / "sample2.zip"
        
        self.assertFalse(zip_path1.exists())
        self.assertFalse(zip_path2.exists())
    
    def test_real_title1_processing(self):
        """Test processing the actual Title 1 file"""
        # Check if the downloaded Title 1 file exists
        title1_path = Path("downloads/title01.zip")
        if not title1_path.exists():
            self.skipTest("Title 1 ZIP file not found. Run download_usc.py first.")
        
        # Copy the Title 1 file to the test downloads directory
        shutil.copy(title1_path, self.test_download_dir / "title01.zip")
        
        # Process the downloads
        self.processor.process_downloads()
        
        # Check if at least one JSON file was created
        json_files = list(self.test_output_dir.glob("*.json"))
        self.assertGreater(len(json_files), 0)
        
        # Verify the content of the first JSON file
        with open(json_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check that the basic structure is correct
        self.assertIn('metadata', data)
        self.assertIn('content', data)

if __name__ == '__main__':
    unittest.main()
