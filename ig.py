# /// script
# dependencies = [
#   "pytesseract",
#   "Pillow",
#   "pillow-heif",
# ]
# ///

import os
import json
import re
import shutil
from pathlib import Path
import pytesseract
from PIL import Image
import pillow_heif

# Register HEIF opener for PIL
pillow_heif.register_heif_opener()

def extract_instagram_handles(text):
    """Extract Instagram handles from text using regex."""
    # Match @ followed by letters, numbers, periods, and underscores
    pattern = r'@[A-Za-z0-9._]+\b'
    return re.findall(pattern, text)

def process_image(image_path):
    """Extract text from image using OCR."""
    try:
        img = Image.open(image_path)
        # Convert image to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        text = pytesseract.image_to_string(img)
        return text
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return ""

def main():
    # Create processed directory if it doesn't exist
    processed_dir = Path('processed')
    processed_dir.mkdir(exist_ok=True)
    
    # Get all image files in current directory
    image_files = []
    for ext in ['.heic', '.jpg', '.jpeg', '.png']:
        image_files.extend(Path('.').glob(f'*{ext}'))
        image_files.extend(Path('.').glob(f'*{ext.upper()}'))

    # Process each image
    with open('instagram_handles.jsonl', 'w', encoding='utf-8') as f:
        for image_path in image_files:
            # Skip files already in processed directory
            if 'processed' in str(image_path):
                continue
                
            print(f"Processing {image_path}")
            text = process_image(image_path)
            handles = extract_instagram_handles(text)
            
            if handles:
                # Write results to JSONL file
                for handle in handles:
                    result = {
                        'file': image_path.name,
                        'ig': handle
                    }
                    f.write(json.dumps(result) + '\n')
                
                # Move file to processed directory
                shutil.move(str(image_path), str(processed_dir / image_path.name))

if __name__ == "__main__":
    main()