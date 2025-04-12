# Handling Encoding Issues in US Code Processing

This guide provides detailed information on how the US Laws Processor handles encoding issues and how to troubleshoot them.

## Understanding Encoding Issues

The US Code XML files are primarily encoded in UTF-8, but may contain characters from different encodings or special characters that can cause processing issues. Common problems include:

1. **Non-UTF-8 Characters**: Characters that are not valid in UTF-8 encoding
2. **Control Characters**: Non-printable characters that can cause parsing issues
3. **Special Symbols**: Legal symbols or formatting characters that may not be properly represented
4. **Mixed Encodings**: Files that contain a mix of different encodings

## How the Application Handles Encoding Issues

The US Laws Processor includes several mechanisms to handle encoding issues:

### 1. Multi-Encoding Support

The application attempts to read files with UTF-8 encoding first, and falls back to Latin-1 (ISO-8859-1) if UTF-8 fails:

```python
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    with open(file_path, 'r', encoding='latin-1') as f:
        content = f.read()
```

### 2. Character Sanitization

When extracting text from XML elements, the application sanitizes problematic characters:

```python
# Sanitize text by re-encoding with error handling
sanitized = text.encode('utf-8', 'ignore').decode('utf-8')
```

### 3. Robust XML Parsing

The XML parser is configured to handle encoding issues gracefully:

```python
try:
    tree = ET.parse(xml_path)
    root = tree.getroot()
except ET.ParseError as e:
    # Handle parsing error
except UnicodeDecodeError as e:
    # Handle encoding error
```

### 4. Fallback Mechanisms

If a specific part of a file cannot be processed due to encoding issues, the application uses fallback mechanisms to ensure the overall processing can continue:

```python
try:
    # Process content
except EncodingError:
    # Use fallback content
    content = "Content unavailable due to encoding issues"
```

## Troubleshooting Specific Encoding Issues

### Issue: UnicodeDecodeError when reading files

**Symptoms**:
- Error message: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x92 in position 1234: invalid start byte`
- Processing fails for specific files

**Solutions**:

1. **Identify the problematic file and character**:
   ```python
   with open(file_path, 'rb') as f:
       content = f.read()
       for i, byte in enumerate(content):
           try:
               byte.to_bytes(1, byteorder='big').decode('utf-8')
           except UnicodeDecodeError:
               print(f"Problematic byte at position {i}: {hex(byte)}")
   ```

2. **Try different encodings**:
   ```python
   encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
   for encoding in encodings:
       try:
           with open(file_path, 'r', encoding=encoding) as f:
               content = f.read()
           print(f"Successfully read with {encoding} encoding")
           break
       except UnicodeDecodeError:
           print(f"Failed with {encoding} encoding")
   ```

3. **Use the chardet library to detect encoding**:
   ```python
   import chardet
   
   with open(file_path, 'rb') as f:
       result = chardet.detect(f.read())
   print(f"Detected encoding: {result['encoding']} with confidence {result['confidence']}")
   ```

4. **Force binary mode and handle encoding manually**:
   ```python
   with open(file_path, 'rb') as f:
       content = f.read()
       # Replace problematic bytes
       content = content.replace(b'\x92', b"'")
       # Then decode
       text = content.decode('utf-8', errors='ignore')
   ```

### Issue: Garbled text in processed JSON files

**Symptoms**:
- Strange characters in the processed JSON files
- Text that looks like: "This is a section�with special�characters"

**Solutions**:

1. **Normalize the text**:
   ```python
   import unicodedata
   
   normalized_text = unicodedata.normalize('NFKD', text)
   ```

2. **Replace specific problematic characters**:
   ```python
   replacements = {
       '\u2013': '-',  # en dash
       '\u2014': '--',  # em dash
       '\u2018': "'",   # left single quote
       '\u2019': "'",   # right single quote
       '\u201c': '"',   # left double quote
       '\u201d': '"',   # right double quote
       '\u00a7': 'S',   # section symbol
       '\u00b6': 'P',   # paragraph symbol
   }
   
   for old, new in replacements.items():
       text = text.replace(old, new)
   ```

3. **Strip non-ASCII characters**:
   ```python
   # Keep only ASCII characters
   ascii_text = ''.join(char for char in text if ord(char) < 128)
   ```

4. **Use a JSON encoder that can handle problematic characters**:
   ```python
   import json
   
   class EncodingFriendlyJSONEncoder(json.JSONEncoder):
       def encode(self, obj):
           if isinstance(obj, str):
               return super().encode(obj.encode('utf-8', 'ignore').decode('utf-8'))
           return super().encode(obj)
   
   with open('output.json', 'w', encoding='utf-8') as f:
       json.dump(data, f, cls=EncodingFriendlyJSONEncoder)
   ```

## Best Practices for Handling Encoding Issues

1. **Always specify encodings explicitly** when opening files:
   ```python
   with open(file_path, 'r', encoding='utf-8') as f:
       # ...
   ```

2. **Use error handlers** when decoding:
   ```python
   text = bytes_content.decode('utf-8', errors='ignore')  # Ignore problematic characters
   # or
   text = bytes_content.decode('utf-8', errors='replace')  # Replace with � character
   ```

3. **Normalize Unicode text**:
   ```python
   import unicodedata
   
   normalized_text = unicodedata.normalize('NFKD', text)
   ```

4. **Log encoding issues** with sufficient context:
   ```python
   try:
       # Process file
   except UnicodeDecodeError as e:
       logger.error(f"Encoding error in {file_path} at position {e.start}: {e}")
       logger.debug(f"Context: {content[max(0, e.start-20):e.start]}|{content[e.start:min(len(content), e.start+20)]}")
   ```

5. **Use binary mode for problematic files**:
   ```python
   with open(file_path, 'rb') as f:
       content = f.read()
       # Process binary content
   ```

## Additional Resources

- [Python Unicode HOWTO](https://docs.python.org/3/howto/unicode.html)
- [Character Encoding in Python](https://realpython.com/python-encodings-guide/)
- [The Absolute Minimum Every Software Developer Must Know About Unicode](https://www.joelonsoftware.com/2003/10/08/the-absolute-minimum-every-software-developer-absolutely-positively-must-know-about-unicode-and-character-sets-no-excuses/)
- [Unicode® Standard Annex #15: Unicode Normalization Forms](https://unicode.org/reports/tr15/)
